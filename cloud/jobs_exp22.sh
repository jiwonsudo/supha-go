#!/usr/bin/env bash
# Experiment 22: how long to wait before each move in the contest game (engine2, JS agent with
# shape (2, 0.6)). Modes none / timers / calm, seeds 0..49 each.
#   SUPHAGO_JOBS=cloud/jobs_exp22.sh bash cloud/run.sh start
cd "$(dirname "$0")/../engine2"
echo "$(date '+%F %T') start experiment 22 on $(nproc) vCPU"
for mode in none timers calm; do for s in $(seq 0 49); do echo "$mode $s"; done; done |
  xargs -P "$(nproc)" -n 2 sh -c 'node test/play_settle.js "$1" 1 "$0" >> "../python/settle_$0.jsonl"'
echo "$(date '+%F %T') done"
date > ../jobs.done
sudo shutdown -h now
