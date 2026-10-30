#!/usr/bin/env bash
# 10-30 21:30: restart experiment 17 with a cheaper rollout (top 6, length 30) so even long
# games finish before 9 in the morning. Stops only the main jobs_takeover.sh shell (its
# subshells keep running the shape benches and the 1-ply n=50 sweep), then shuts the VM
# down once every bench and sweep is done.
cd "$(dirname "$0")/../python"
echo "$(date '+%F %T') restart rollout search (top 6, count 8, length 30)"
kill -KILL "$(pgrep -o -f '[j]obs_takeover')" 2>/dev/null
pkill -f "[a]gent ro --top 8" && sleep 5
nice -n 0 python3 -m suphago.bench --agent ro --top 6 --count 8 --length 30 --games 30 --workers 30 \
  --out ro_t6_c8_l30.jsonl > ro_t6_c8_l30.log 2>&1 &
sleep 30
while pgrep -f "[s]uphago\.(bench|sweep)" >/dev/null || pgrep -f "[j]obs_takeover" >/dev/null; do sleep 60; done
echo "$(date '+%F %T') all done"
date > ../jobs.done
sudo shutdown -h now
