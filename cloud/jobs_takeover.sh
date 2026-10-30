#!/usr/bin/env bash
# 10-30 night: takes over the running VM (jobs_sweep_all.sh, then jobs_s2_after.sh) and adds
# the Mac's experiments 16 and 17, aiming to finish everything around 9 in the morning (KST).
# Priorities (nice): rollout search 0 > shape terms 5 = 1-ply n=50 5 > s2 sweep 10.
# Experiment 14 is cut to seeds 0..29 (games already played are kept).
cd "$(dirname "$0")/../python"
echo "$(date '+%F %T') takeover on $(nproc) vCPU"
pkill -KILL -f "[j]obs_s2_after"                      # its shutdown is now ours
pkill -f "[s]uphago.sweep --configs 2:50:6" && sleep 5 # restarted below with fewer seeds

nice -n 0 python3 -m suphago.bench --agent ro --top 8 --count 8 --length 40 --games 30 --workers 30 \
  --out ro_t8_c8_l40.jsonl > ro_t8_c8_l40.log 2>&1 &
P1=$!
( nice -n 5 python3 -m suphago.bench --agent mc --plies 2 --chain 1 --inv 0.3 --games 50 --workers 16 \
    --out shape_c1_i03.jsonl > shape_c1_i03.log 2>&1
  nice -n 5 python3 -m suphago.bench --agent mc --plies 2 --chain 2 --inv 0.6 --games 50 --workers 16 \
    --out shape_c2_i06.jsonl > shape_c2_i06.log 2>&1 ) &
P2=$!
nice -n 10 python3 -m suphago.sweep --configs 2:50:6 2:25:3 --seeds 0 29 --workers 30 \
  --out sweep_s2.jsonl >> sweep_s2.log 2>&1 &
P3=$!
( while pgrep -f "suphago.sweep --configs 1:25:1" >/dev/null; do sleep 60; done
  echo "$(date '+%F %T') main sweep finished, 1-ply n=50 seeds 30..49"
  nice -n 5 python3 -m suphago.sweep --configs 1:50:1 --seeds 30 49 --workers 8 --out sweep.jsonl >> sweep.log 2>&1
  echo "$(date '+%F %T') done sweep" ) &
P4=$!

wait $P1; echo "$(date '+%F %T') done rollout"
wait $P2; echo "$(date '+%F %T') done shape"
wait $P3; echo "$(date '+%F %T') done s2 sweep"
wait $P4
date > ../jobs.done
sudo shutdown -h now
