#!/usr/bin/env bash
# Experiment 19: three ways to strengthen the board-shape terms (chain 1, inv 0.3), each on
# seeds 0..99, compared with the plain shape agent on the same seeds (experiments 16, 18).
#   SUPHAGO_JOBS=cloud/jobs_exp19.sh bash cloud/run.sh start
cd "$(dirname "$0")/../python"
W=$(( $(nproc) / 4 ))
echo "$(date '+%F %T') start experiment 19 on $(nproc) vCPU, $W workers each"
run() { name=$1; shift
  python3 -m suphago.bench --agent mc --plies 2 --chain 1 --inv 0.3 "$@" --games 100 --workers "$W" \
    --out "$name.jsonl" > "$name.log" 2>&1
  echo "$(date '+%F %T') done $name"; }
run shape_long1 --long 1 &
run shape_small05 --small 0.5 &
run shape_long1_small05 --long 1 --small 0.5 &
run shape_f240 --frames 240 &
wait
date > ../jobs.done
sudo shutdown -h now
