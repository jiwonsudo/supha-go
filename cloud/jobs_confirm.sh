#!/usr/bin/env bash
# 10-31 05:00: stop experiment 17 (rollouts too slow, 8 of 30 games in 8 hours) and use its
# cores for experiment 18: the board-shape terms of experiment 16 on new seeds 50..99,
# and a lower weight (0.5, 0.15) on seeds 0..49. Takes over the VM shutdown from
# jobs_takeover.sh (its subshells keep running the second shape bench and the s2 sweep).
cd "$(dirname "$0")/../python"
echo "$(date '+%F %T') stop rollout search, start experiment 18"
kill -KILL "$(pgrep -o -f '[j]obs_takeover')" 2>/dev/null
pkill -f "[a]gent ro --top" && sleep 5
python3 -m suphago.bench --agent mc --plies 2 --chain 1 --inv 0.3 --games 50 --seed 50 --workers 25 \
  --out shape_c1_i03_s50.jsonl > shape_c1_i03_s50.log 2>&1 &
python3 -m suphago.bench --agent mc --plies 2 --chain 0.5 --inv 0.15 --games 50 --workers 25 \
  --out shape_c05_i015.jsonl > shape_c05_i015.log 2>&1 &
sleep 30
while pgrep -f "[s]uphago\.(bench|sweep)" >/dev/null || pgrep -f "[j]obs_takeover" >/dev/null; do sleep 60; done
echo "$(date '+%F %T') all done"
date > ../jobs.done
sudo shutdown -h now
