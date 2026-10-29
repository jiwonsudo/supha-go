#!/usr/bin/env bash
# Mac jobs for the night of 2026-10-29 (about 6.5 hours).
#   caffeinate -i nohup bash cloud/night2.sh > night2.log 2>&1 &
cd "$(dirname "$0")/../python"
[ -f ../.venv/bin/activate ] && . ../.venv/bin/activate
command -v python >/dev/null || { echo "python not found: activate the venv first"; exit 1; }
step() { echo "$(date '+%F %T') start $1"; shift; "$@"; local rc=$?; echo "$(date '+%F %T') done (exit $rc)"; }

# 1. big-fruit bonus x5 on 2-ply (x1 gave 4121; plain 2-ply 4080) (about 45 min)
step bench_mc2_pw5 python -m suphago.bench --agent mc --plies 2 --pair 5 --wm 5 --games 30 --workers 10 \
  --out bench_mc2_pw5.jsonl > bench_mc2_pw5.log 2>&1

# 2. finish the branch games (187 of 800 done) (about 45 min)
step collect_branch python -m suphago.collect_branch --data ../data/mc1 ../data/mc2 --branches 800 --length 40 \
  --workers 10 --out ../data/branch --resume > collect_branch2.log 2>&1

# 3. value net v3: points in the next 30 moves, with branch boards, dropout, weight decay (about 90 min)
step train_v3 python -m suphago.train_value --data ../data/mc1 ../data/mc2 ../data/branch --horizon 30 --over-head \
  --epochs 15 --dropout 0.2 --wd 0.01 --loader-workers 8 --out ../runs/value_v3.pt > train_v3.log 2>&1

# 4. value net v4: points until the game ends, so a watermelon clear (300 more moves) counts.
#    Branch games are left out: most stop before the game ends, and keeping only the ones
#    that ended would teach the network that random moves always lose. (about 75 min)
step train_v4 python -m suphago.train_value --data ../data/mc1 ../data/mc2 --horizon 0 --over-head \
  --epochs 15 --dropout 0.2 --wd 0.01 --loader-workers 8 --out ../runs/value_v4.pt > train_v4.log 2>&1

# 5. helper benches (last night: mcv 1-ply with value_h30_all 4036)
step bench_mcv1_v3 python -m suphago.bench --agent mcv --model ../runs/value_v3.pt --alpha 1 --risk 1 \
  --games 30 --workers 10 --out bench_mcv1_v3.jsonl > bench_mcv1_v3.log 2>&1
step bench_mcv2_v3 python -m suphago.bench --agent mcv --plies 2 --model ../runs/value_v3.pt --alpha 1 --risk 1 \
  --games 30 --workers 10 --out bench_mcv2_v3.jsonl > bench_mcv2_v3.log 2>&1
step bench_mcv2_v4 python -m suphago.bench --agent mcv --plies 2 --model ../runs/value_v4.pt --alpha 1 --risk 1 \
  --games 30 --workers 10 --out bench_mcv2_v4.jsonl > bench_mcv2_v4.log 2>&1

echo "$(date '+%F %T') night2 jobs finished"
