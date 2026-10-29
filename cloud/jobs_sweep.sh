#!/usr/bin/env bash
# Cloud half of the search-budget sweep (about 6 hours on 64 vCPU). Started by:
#   SUPHAGO_JOBS=cloud/jobs_sweep.sh bash cloud/run.sh start
# 2-ply Monte Carlo with more candidates (n) and more second drops (s2), seeds 0..49.
# (2-ply n=50 s2=1 already has seeds 0..99.)
cd "$(dirname "$0")/../python"
W=$(nproc)
echo "$(date '+%F %T') start sweep"
python3 -m suphago.sweep --configs 2:25:1 2:100:1 2:200:1 2:50:3 --seeds 0 49 --workers "$W" \
  --out sweep_cloud.jsonl > sweep_cloud.log 2>&1
echo "$(date '+%F %T') done sweep (exit $?)"
date > ../jobs.done
sudo shutdown -h now
