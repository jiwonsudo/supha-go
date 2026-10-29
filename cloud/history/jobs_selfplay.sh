#!/usr/bin/env bash
# Cloud jobs for the night of 2026-10-30 (about 5 to 6 hours on 64 vCPU). Started by:
#   SUPHAGO_JOBS=cloud/jobs_selfplay.sh bash cloud/run.sh start
# 1. self-play data: 200 games by the mcv 1-ply + value_v3 agent (first round of the loop)
# 2. bigger baselines on seeds 30..99 (with the existing 0..29 -> 100 games each):
#    Monte Carlo 2-ply, and mcv 2-ply + value_v4 (highest median so far)
cd "$(dirname "$0")/../python"
W=$(nproc)
step() { local name=$1 log=$2; shift 2; echo "$(date '+%F %T') start $name"; "$@" > "$log" 2>&1; local rc=$?; echo "$(date '+%F %T') done $name (exit $rc)"; }

step collect_sp1 collect_sp1.log python3 -m suphago.collect --agent mcv --model ../runs/value_v3.pt --alpha 1 --risk 1 \
  --games 200 --seed 200000 --workers "$W" --out ../data/sp1
step bench_mc2_more bench_mc2_more.log python3 -m suphago.bench --agent mc --plies 2 --games 70 --seed 30 \
  --workers "$W" --out bench_mc2_more.jsonl
step bench_mcv2_v4_more bench_mcv2_v4_more.log python3 -m suphago.bench --agent mcv --plies 2 --model ../runs/value_v4.pt \
  --alpha 1 --risk 1 --games 70 --seed 30 --workers "$W" --out bench_mcv2_v4_more.jsonl

date > ../jobs.done
echo "all done; shutting down"
sudo shutdown -h now
