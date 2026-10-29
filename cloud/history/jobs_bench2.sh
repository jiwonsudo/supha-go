#!/usr/bin/env bash
# Cloud benches for 2026-10-29 evening (about 1.5 hours on 64 vCPU), two at the same time:
#   mcv 2-ply with value_v4 (to the end of the game) and with value_h30_all (30 moves, last night's model).
#   SUPHAGO_JOBS=cloud/jobs_bench2.sh bash cloud/run.sh start
cd "$(dirname "$0")/../python"
W=$(nproc); H=$((W / 2))
step() { echo "$(date '+%F %T') start $1"; shift; "$@"; local rc=$?; echo "$(date '+%F %T') done (exit $rc)"; }

step bench_mcv2_v4 python3 -m suphago.bench --agent mcv --plies 2 --model ../runs/value_v4.pt --alpha 1 --risk 1 \
  --games 30 --workers $((H < 30 ? H : 30)) --out bench_mcv2_v4.jsonl > bench_mcv2_v4.log 2>&1 &
step bench_mcv2_h30all python3 -m suphago.bench --agent mcv --plies 2 --model ../runs/value_h30_all.pt --alpha 1 --risk 1 \
  --games 30 --workers $((H < 30 ? H : 30)) --out bench_mcv2_h30all.jsonl > bench_mcv2_h30all.log 2>&1 &
wait

date > ../jobs.done
echo "all done; shutting down"
sudo shutdown -h now
