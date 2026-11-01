#!/usr/bin/env bash
# Experiment 21: contest game (engine2), seeds 0..99. Real-point term, stronger shape terms,
# and how much a taller window (phone-like 9:19.5, winH 1560) is worth.
#   SUPHAGO_JOBS=cloud/jobs_exp21.sh bash cloud/run.sh start
cd "$(dirname "$0")/../python"
export SUPHAGO_ENGINE=2
W=$(( $(nproc) / 5 ))
echo "$(date '+%F %T') start experiment 21 on $(nproc) vCPU, $W workers each"
run() { name=$1; shift
  python3 -m suphago.bench --agent mc --plies 2 --games 100 --workers "$W" "$@" --out "$name.jsonl" > "$name.log" 2>&1
  echo "$(date '+%F %T') done $name"; }
run e2_double_g03 --chain 2 --inv 0.6 --gain 0.3 &
run e2_double_g1 --chain 2 --inv 0.6 --gain 1 &
run e2_triple --chain 3 --inv 0.9 &
run e2_double_tall --chain 2 --inv 0.6 --winh 1560 &
run e2_mc2_tall --winh 1560 &
wait
date > ../jobs.done
sudo shutdown -h now
