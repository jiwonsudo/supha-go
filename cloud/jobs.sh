#!/usr/bin/env bash
# Jobs run on the cloud VM by cloud/run.sh. Each step logs to python/<name>.log.
# A failed step does not stop the next one. The VM shuts down at the end.
cd "$(dirname "$0")/../python"
W=$(nproc)
step() { echo "$(date '+%F %T') start $1"; shift; "$@"; echo "$(date '+%F %T') done (exit $?)"; }

step bench_value_mc1 python3 -m suphago.bench --agent value --model ../runs/value_mc1.pt \
  --games 30 --workers "$W" --out bench_value_mc1.jsonl > bench_value_mc1.log 2>&1
step bench_h30_r1 python3 -m suphago.bench --agent value --model ../runs/value_h30.pt --risk 1 \
  --games 30 --workers "$W" --out bench_h30_r1.jsonl > bench_h30_r1.log 2>&1
step bench_h30_r1_b10 python3 -m suphago.bench --agent value --model ../runs/value_h30.pt --risk 1 --blend 10 \
  --games 30 --workers "$W" --out bench_h30_r1_b10.jsonl > bench_h30_r1_b10.log 2>&1
step collect_mc2 python3 -m suphago.collect --agent mc --plies 2 --games 200 --workers "$W" \
  --out ../data/mc2 > collect_mc2.log 2>&1

date > ../jobs.done
echo "all done; shutting down"
sudo shutdown -h now
