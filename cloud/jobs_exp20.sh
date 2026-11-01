#!/usr/bin/env bash
# Experiment 20: settings for the contest-site game (engine2, SUPHAGO_ENGINE=2), seeds 0..99.
#   SUPHAGO_JOBS=cloud/jobs_exp20.sh bash cloud/run.sh start
# Scores are internal points; the site shows twice that (docs/contest-site.md).
cd "$(dirname "$0")/../python"
export SUPHAGO_ENGINE=2
node ../engine2/test/smoke.js > ../engine2_smoke.log 2>&1
W=$(( $(nproc) / 5 ))
echo "$(date '+%F %T') start experiment 20 on $(nproc) vCPU, $W workers each"
run() { name=$1; shift
  python3 -m suphago.bench --agent mc --games 100 --workers "$W" "$@" --out "$name.jsonl" > "$name.log" 2>&1
  echo "$(date '+%F %T') done $name"; }
run e2_mc2 --plies 2 &
run e2_shape --plies 2 --chain 1 --inv 0.3 &
run e2_shape_half --plies 2 --chain 0.5 --inv 0.15 &
run e2_shape_double --plies 2 --chain 2 --inv 0.6 &
run e2_mc1_shape --plies 1 --chain 1 --inv 0.3 &
wait
date > ../jobs.done
sudo shutdown -h now
