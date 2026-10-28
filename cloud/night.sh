#!/usr/bin/env bash
# Next-step jobs for the Mac, run right after the overnight collection (2026-10-29).
# Run from the repo root inside the venv. Logs go to python/*.log.
cd "$(dirname "$0")/../python"
step() { echo "$(date '+%F %T') start $1"; shift; "$@"; echo "$(date '+%F %T') done (exit $?)"; }

# 1. value net on all 1-ply + 2-ply games collected so far (30-move target + game-over head)
step train_h30_all python -m suphago.train_value --data ../data/mc1 ../data/mc2 --horizon 30 --over-head \
  --epochs 15 --loader-workers 8 --out ../runs/value_h30_all.pt > train_h30_all.log 2>&1
MODEL=../runs/value_h30_all.pt
[ -f "$MODEL" ] || MODEL=../runs/value_h30.pt

# 2. Monte Carlo baseline with the network as a helper (same 120-frame look-ahead and
#    heuristic; network breaks ties and penalizes boards that are about to end).
step bench_mcv_a1_r1 python -m suphago.bench --agent mcv --model "$MODEL" --alpha 1 --risk 1 \
  --games 30 --workers 10 --out bench_mcv_a1_r1.jsonl > bench_mcv_a1_r1.log 2>&1

# 3. only the game-over penalty, no value term
step bench_mcv_a0_r1 python -m suphago.bench --agent mcv --model "$MODEL" --alpha 0 --risk 1 \
  --games 30 --workers 10 --out bench_mcv_a0_r1.jsonl > bench_mcv_a0_r1.log 2>&1

echo "$(date '+%F %T') night jobs finished"
