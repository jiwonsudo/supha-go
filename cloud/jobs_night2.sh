#!/usr/bin/env bash
# Cloud half of the 2026-10-29 night run (about 1 hour on 64 vCPU). Started by:
#   SUPHAGO_JOBS=cloud/jobs_night2.sh SUPHAGO_DATA="mc1 mc2 branch" bash cloud/run.sh start
# Runs at the same time: the 2-ply bonus x5 bench (30 workers) and the rest of the
# branch games (the other vCPUs). The VM shuts down at the end.
cd "$(dirname "$0")/../python"
W=$(nproc)
step() { echo "$(date '+%F %T') start $1"; shift; "$@"; local rc=$?; echo "$(date '+%F %T') done (exit $rc)"; }

step bench_mc2_pw5 python3 -m suphago.bench --agent mc --plies 2 --pair 5 --wm 5 --games 30 --workers 30 \
  --out bench_mc2_pw5.jsonl > bench_mc2_pw5.log 2>&1 &
step collect_branch python3 -m suphago.collect_branch --data ../data/mc1 ../data/mc2 --branches 800 --length 40 \
  --workers $((W > 34 ? W - 30 : 4)) --out ../data/branch --resume > collect_branch2.log 2>&1 &
wait

date > ../jobs.done
echo "all done; shutting down"
sudo shutdown -h now
