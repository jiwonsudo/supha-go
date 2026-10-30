#!/usr/bin/env bash
# Experiment 15 on the Mac (under an hour with 10 workers). Run once from the repo root:
#   caffeinate -i nohup bash cloud/wait_mac.sh > wait_mac.log 2>&1 &
# Same Monte Carlo agents, but each next drop waits 84 more frames (120 in total, the same
# length the search simulates) instead of dropping the moment the cooldown ends.
# Compared against the no-wait games already played on the same seeds.
cd "$(dirname "$0")/../python"
[ -f ../.venv/bin/activate ] && . ../.venv/bin/activate
command -v python >/dev/null || { echo "python not found: activate the venv first"; exit 1; }
LOCK=../.wait_mac.lock
mkdir "$LOCK" 2>/dev/null || { echo "wait_mac is already running (remove $LOCK if it is not)"; exit 1; }
trap 'rmdir "$LOCK"' EXIT
echo "$(date '+%F %T') start"
python -m suphago.sweep --configs 2:50:1 1:50:1 --seeds 0 49 --wait 84 --workers 10 --out sweep_wait84.jsonl > wait_mac_run.log 2>&1
echo "$(date '+%F %T') done"
