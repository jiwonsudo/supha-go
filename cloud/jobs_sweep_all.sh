#!/usr/bin/env bash
# The whole search-budget sweep on one cloud VM (about 8 hours on 64 vCPU, 4 on 128). Started by:
#   SUPHAGO_JOBS=cloud/jobs_sweep_all.sh bash cloud/run.sh start
# Seeds 0..49 for every setting (1-ply n=50 only needs 30..49: 0..29 were played before;
# 2-ply n=50 s2=1 already has 0..99). One shared queue, biggest games first.
cd "$(dirname "$0")/../python"
W=$(nproc)
echo "$(date '+%F %T') start sweep on $W vCPU"
python3 -m suphago.sweep --configs 1:25:1 1:100:1 1:200:1 2:25:1 2:100:1 2:200:1 2:50:3 --seeds 0 49 \
  --workers "$W" --out sweep.jsonl > sweep.log 2>&1
python3 -m suphago.sweep --configs 1:50:1 --seeds 30 49 --workers "$W" --out sweep.jsonl >> sweep.log 2>&1
echo "$(date '+%F %T') done sweep"
date > ../jobs.done
sudo shutdown -h now
