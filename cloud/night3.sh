#!/usr/bin/env bash
# Mac jobs for the night of 2026-10-30 (about 5 hours). Run once from the repo root:
#   caffeinate -i nohup bash cloud/night3.sh > night3.log 2>&1 &
# Each step's output goes to python/<log>; this file only gets start/done lines.
cd "$(dirname "$0")/../python"
[ -f ../.venv/bin/activate ] && . ../.venv/bin/activate
command -v python >/dev/null || { echo "python not found: activate the venv first"; exit 1; }
# refuse to run twice at the same time (last time two copies ran and everything took twice as long)
LOCK=../.night3.lock
mkdir "$LOCK" 2>/dev/null || { echo "night3 is already running (remove $LOCK if it is not)"; exit 1; }
trap 'rmdir "$LOCK"' EXIT
step() { local name=$1 log=$2; shift 2; echo "$(date '+%F %T') start $name"; "$@" > "$log" 2>&1; local rc=$?; echo "$(date '+%F %T') done $name (exit $rc)"; }

# 1. policy network on the Monte Carlo moves (GPU, about 70 min)
step train_policy train_policy_v1.log python -m suphago.train_policy --data ../data/mc1 ../data/mc2 \
  --epochs 10 --loader-workers 8 --out ../runs/policy_v1.pt

# 2. policy-guided 2-ply search with the value helper (about 70 min)
step bench_ps_v3 bench_ps_v3.log python -m suphago.bench --agent ps --policy ../runs/policy_v1.pt \
  --model ../runs/value_v3.pt --alpha 1 --risk 1 --games 30 --workers 10 --out bench_ps_v3.jsonl

# 3. the same search without the value network: does the search structure alone help? (about 60 min)
step bench_ps bench_ps.log python -m suphago.bench --agent ps --policy ../runs/policy_v1.pt \
  --games 30 --workers 10 --out bench_ps.jsonl

# 4. more games for mcv 1-ply + v3 (seeds 30..99), so it has 100 like MC 2-ply (about 90 min)
step bench_mcv1_v3_more bench_mcv1_v3_more.log python -m suphago.bench --agent mcv --model ../runs/value_v3.pt \
  --alpha 1 --risk 1 --games 70 --seed 30 --workers 10 --out bench_mcv1_v3_more.jsonl

echo "$(date '+%F %T') night3 jobs finished"
