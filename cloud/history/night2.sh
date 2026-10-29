#!/usr/bin/env bash
# Mac half of the 2026-10-29 night run (about 5 hours). The cloud does the bonus bench and
# the rest of the branch games (cloud/jobs_night2.sh); this waits for those branch games.
#   caffeinate -i nohup bash cloud/night2.sh > night2.log 2>&1 &
cd "$(dirname "$0")/../python"
[ -f ../.venv/bin/activate ] && . ../.venv/bin/activate
command -v python >/dev/null || { echo "python not found: activate the venv first"; exit 1; }
step() { echo "$(date '+%F %T') start $1"; shift; "$@"; local rc=$?; echo "$(date '+%F %T') done (exit $rc)"; }
branches() { python -c "from suphago.collect import load_games; print(sum(1 for _ in load_games('../data/branch')))" 2>/dev/null || echo 0; }

# 1. value net v4: points until the game ends, so a watermelon clear (300 more moves) counts.
#    Branch games are left out: most stop before the game ends, and keeping only the ones
#    that ended would teach the network that random moves always lose. (about 75 min)
step train_v4 python -m suphago.train_value --data ../data/mc1 ../data/mc2 --horizon 0 --over-head \
  --epochs 15 --dropout 0.2 --wd 0.01 --loader-workers 8 --out ../runs/value_v4.pt > train_v4.log 2>&1

# 2. helper on 2-ply with v4 (plain 2-ply 4080) (about 45 min)
step bench_mcv2_v4 python -m suphago.bench --agent mcv --plies 2 --model ../runs/value_v4.pt --alpha 1 --risk 1 \
  --games 30 --workers 10 --out bench_mcv2_v4.jsonl > bench_mcv2_v4.log 2>&1

# 3. wait for the cloud branch games (bash cloud/run.sh fetch copies them into data/branch).
#    After 2 hours without them, collect the rest here.
for i in $(seq 1 120); do
  n=$(branches); [ "$n" -ge 800 ] && break
  [ "$i" = 1 ] && echo "$(date '+%F %T') waiting for branch games ($n/800); run: bash cloud/run.sh fetch"
  sleep 60
done
if [ "$(branches)" -lt 800 ]; then
  step collect_branch python -m suphago.collect_branch --data ../data/mc1 ../data/mc2 --branches 800 --length 40 \
    --workers 10 --out ../data/branch --resume > collect_branch2.log 2>&1
fi

# 4. value net v3: points in the next 30 moves, with branch boards, dropout, weight decay (about 90 min)
step train_v3 python -m suphago.train_value --data ../data/mc1 ../data/mc2 ../data/branch --horizon 30 --over-head \
  --epochs 15 --dropout 0.2 --wd 0.01 --loader-workers 8 --out ../runs/value_v3.pt > train_v3.log 2>&1

# 5. helper benches with v3 (last night: mcv 1-ply 4036) (about 85 min)
step bench_mcv1_v3 python -m suphago.bench --agent mcv --model ../runs/value_v3.pt --alpha 1 --risk 1 \
  --games 30 --workers 10 --out bench_mcv1_v3.jsonl > bench_mcv1_v3.log 2>&1
step bench_mcv2_v3 python -m suphago.bench --agent mcv --plies 2 --model ../runs/value_v3.pt --alpha 1 --risk 1 \
  --games 30 --workers 10 --out bench_mcv2_v3.jsonl > bench_mcv2_v3.log 2>&1

echo "$(date '+%F %T') night2 jobs finished"
