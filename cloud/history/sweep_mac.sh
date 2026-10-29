#!/usr/bin/env bash
# Mac half of the search-budget sweep (about 5 hours). Run once from the repo root:
#   caffeinate -i nohup bash cloud/sweep_mac.sh > sweep_mac.log 2>&1 &
# 1-ply Monte Carlo with 25 / 100 / 200 candidates on seeds 0..49, and 50 candidates on
# seeds 30..49 (0..29 were played before). Can be started again: finished games are kept.
cd "$(dirname "$0")/../python"
[ -f ../.venv/bin/activate ] && . ../.venv/bin/activate
command -v python >/dev/null || { echo "python not found: activate the venv first"; exit 1; }
LOCK=../.sweep_mac.lock
mkdir "$LOCK" 2>/dev/null || { echo "sweep_mac is already running (remove $LOCK if it is not)"; exit 1; }
trap 'rmdir "$LOCK"' EXIT
echo "$(date '+%F %T') start"
python -m suphago.sweep --configs 1:25:1 1:100:1 1:200:1 --seeds 0 49 --workers 10 --out sweep_mac.jsonl > sweep_mac_run.log 2>&1
python -m suphago.sweep --configs 1:50:1 --seeds 30 49 --workers 10 --out sweep_mac.jsonl >> sweep_mac_run.log 2>&1
echo "$(date '+%F %T') done"
