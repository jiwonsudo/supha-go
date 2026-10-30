#!/usr/bin/env bash
# Experiment 14, added to the VM that is already running jobs_sweep_all.sh (10-30).
# That script is stopped first (its sweep keeps running) so it does not shut the VM down;
# this one takes over the rest of its work, then shuts the VM down.
# The new sweep runs at lowest priority, so it only uses cores the main sweep leaves idle.
cd "$(dirname "$0")/../python"
W=$(nproc)
MAIN="suphago.sweep --configs 1:25:1"
echo "$(date '+%F %T') start s2 sweep (low priority) on $W vCPU"
nice -n 19 python3 -m suphago.sweep --configs 2:50:6 2:25:3 --seeds 0 49 --workers "$W" \
  --out sweep_s2.jsonl > sweep_s2.log 2>&1 &
S2=$!
while pgrep -f "$MAIN" >/dev/null; do sleep 60; done
echo "$(date '+%F %T') main sweep finished, 1-ply n=50 seeds 30..49"
python3 -m suphago.sweep --configs 1:50:1 --seeds 30 49 --workers "$W" --out sweep.jsonl >> sweep.log 2>&1
echo "$(date '+%F %T') done sweep"
wait "$S2"
echo "$(date '+%F %T') done s2 sweep"
date > ../jobs.done
sudo shutdown -h now
