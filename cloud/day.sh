#!/usr/bin/env bash
# Mac jobs for 2026-10-29 (about 4.5 hours). Run from the repo root inside the venv:
#   nohup bash cloud/day.sh > day.log 2>&1 &
# Logs go to python/*.log.
cd "$(dirname "$0")/../python"
# use the repo venv even when it is not activated in this shell
[ -f ../.venv/bin/activate ] && . ../.venv/bin/activate
command -v python >/dev/null || { echo "python not found: activate the venv first"; exit 1; }
step() { echo "$(date '+%F %T') start $1"; shift; "$@"; local rc=$?; echo "$(date '+%F %T') done (exit $rc)"; }

# 1. boards after a random (bad) move, then 40 Monte Carlo moves (about 75 min)
step collect_branch python -m suphago.collect_branch --data ../data/mc1 ../data/mc2 --branches 800 --length 40 \
  --workers 10 --out ../data/branch > collect_branch.log 2>&1

# 2. value net on everything: 1-ply 100 + 2-ply 211 + branches, with dropout and stronger weight decay (about 100 min)
step train_v3 python -m suphago.train_value --data ../data/mc1 ../data/mc2 ../data/branch --horizon 30 --over-head \
  --epochs 15 --dropout 0.2 --wd 0.01 --loader-workers 8 --out ../runs/value_v3.pt > train_v3.log 2>&1
MODEL=../runs/value_v3.pt
[ -f "$MODEL" ] || MODEL=../runs/value_h30_all.pt

# 3. same 1-ply helper agent as last night (4036 with value_h30_all.pt), new network (about 40 min)
step bench_mcv1_v3 python -m suphago.bench --agent mcv --model "$MODEL" --alpha 1 --risk 1 \
  --games 30 --workers 10 --out bench_mcv1_v3.jsonl > bench_mcv1_v3.log 2>&1

# 4. helper on top of the 2-ply search (baseline 2-ply: 4080) (about 55 min)
step bench_mcv2_v3 python -m suphago.bench --agent mcv --plies 2 --model "$MODEL" --alpha 1 --risk 1 \
  --games 30 --workers 10 --out bench_mcv2_v3.jsonl > bench_mcv2_v3.log 2>&1

echo "$(date '+%F %T') day jobs finished"
