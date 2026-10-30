#!/usr/bin/env bash
# Experiment 14 on the Mac (about 5-6 hours with 10 workers). Run once from the repo root:
#   caffeinate -i nohup bash cloud/sweep_s2_mac.sh > sweep_s2_mac.log 2>&1 &
# Does looking at more second drops (s2) help more than more first-move candidates (n)?
# 2:25:3 costs 150 (between 2:50:1 and 2:100:1), 2:50:6 costs 600 (2:50:3 doubled).
# Seeds 0..29. Can be started again: finished games are kept.
cd "$(dirname "$0")/../python"
[ -f ../.venv/bin/activate ] && . ../.venv/bin/activate
command -v python >/dev/null || { echo "python not found: activate the venv first"; exit 1; }
LOCK=../.sweep_s2_mac.lock
mkdir "$LOCK" 2>/dev/null || { echo "sweep_s2_mac is already running (remove $LOCK if it is not)"; exit 1; }
trap 'rmdir "$LOCK"' EXIT
echo "$(date '+%F %T') start"
python -m suphago.sweep --configs 2:50:6 2:25:3 --seeds 0 29 --workers 10 --out sweep_s2_mac.jsonl > sweep_s2_mac_run.log 2>&1
echo "$(date '+%F %T') done"
