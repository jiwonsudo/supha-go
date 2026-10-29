#!/usr/bin/env bash
# Monte Carlo with the big-fruit terms (watermelon building), 1-ply and 2-ply, 30 games each (about 75 min).
#   caffeinate -i nohup bash cloud/pair.sh > pair.log 2>&1 &
# Compare with mc 1-ply 3556 / 2-ply 4080. Games of 600+ turns are the ones that cleared two watermelons.
cd "$(dirname "$0")/../python"
[ -f ../.venv/bin/activate ] && . ../.venv/bin/activate
command -v python >/dev/null || { echo "python not found: activate the venv first"; exit 1; }
step() { echo "$(date '+%F %T') start $1"; shift; "$@"; local rc=$?; echo "$(date '+%F %T') done (exit $rc)"; }

step bench_mc1_pw python -m suphago.bench --agent mc --pair 1 --wm 1 --games 30 --workers 10 \
  --out bench_mc1_pw.jsonl > bench_mc1_pw.log 2>&1
step bench_mc2_pw python -m suphago.bench --agent mc --plies 2 --pair 1 --wm 1 --games 30 --workers 10 \
  --out bench_mc2_pw.jsonl > bench_mc2_pw.log 2>&1
echo "$(date '+%F %T') pair jobs finished"
