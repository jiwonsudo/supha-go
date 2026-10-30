#!/usr/bin/env bash
# Experiment 16 on the Mac (about 2 hours with 10 workers). Run once from the repo root:
#   caffeinate -i nohup bash cloud/shape_mac.sh > shape_mac.log 2>&1 &
# Monte Carlo 2-ply with the two board-shape terms from experiment 9 added to the score
# (touching fruits one size apart +, big fruit on top of a much smaller one -), at two weights.
# Seeds 0..49, compared with plain MC 2-ply on the same seeds. Waits for wait_mac.sh to finish.
cd "$(dirname "$0")/../python"
[ -f ../.venv/bin/activate ] && . ../.venv/bin/activate
command -v python >/dev/null || { echo "python not found: activate the venv first"; exit 1; }
LOCK=../.shape_mac.lock
mkdir "$LOCK" 2>/dev/null || { echo "shape_mac is already running (remove $LOCK if it is not)"; exit 1; }
trap 'rmdir "$LOCK"' EXIT
while [ -d ../.wait_mac.lock ]; do sleep 60; done
echo "$(date '+%F %T') start"
python -m suphago.bench --agent mc --plies 2 --chain 1 --inv 0.3 --games 50 --workers 10 \
  --out shape_c1_i03.jsonl > shape_c1_i03.log 2>&1
python -m suphago.bench --agent mc --plies 2 --chain 2 --inv 0.6 --games 50 --workers 10 \
  --out shape_c2_i06.jsonl > shape_c2_i06.log 2>&1
echo "$(date '+%F %T') done"
