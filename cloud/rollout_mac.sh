#!/usr/bin/env bash
# Experiment 17, gate 1 of the 30000-point plan, on the Mac overnight. Run once from the repo root:
#   caffeinate -i nohup bash cloud/rollout_mac.sh > rollout_mac.log 2>&1 &
# Rollout search (--agent ro): each of the 8 best 1-ply drops is played out 8 times for
# 40 more moves by a fast policy, on fresh random fruits. Seeds 0..29, compared with
# MC 2-ply on the same seeds by clears (two watermelons merged) and moves survived.
# Waits for shape_mac.sh (and wait_mac.sh) to finish first.
cd "$(dirname "$0")/../python"
[ -f ../.venv/bin/activate ] && . ../.venv/bin/activate
command -v python >/dev/null || { echo "python not found: activate the venv first"; exit 1; }
LOCK=../.rollout_mac.lock
mkdir "$LOCK" 2>/dev/null || { echo "rollout_mac is already running (remove $LOCK if it is not)"; exit 1; }
trap 'rmdir "$LOCK"' EXIT
while [ -d ../.wait_mac.lock ] || [ -d ../.shape_mac.lock ]; do sleep 60; done
echo "$(date '+%F %T') start"
python -m suphago.bench --agent ro --top 8 --count 8 --length 40 --games 30 --workers 10 \
  --out ro_t8_c8_l40.jsonl > ro_t8_c8_l40.log 2>&1
echo "$(date '+%F %T') done"
