"""Branch games: teach the value network what happens after bad moves.

Monte Carlo game records only contain boards reached by good moves, but during search
the network has to score boards after every candidate, many of them bad. This script
takes boards from recorded games, makes one random drop there (the "off-policy" move),
then lets the Monte Carlo agent play on for a fixed number of moves.

    python -m suphago.collect_branch --data ../data/mc1 ../data/mc2 --branches 600 --workers 10 --out ../data/branch

Each output line has the same format as collect.py, plus "ended" (False when the
branch was cut off rather than lost). The first step is the board right after the
random drop, which is what search sees. Targets are only built for steps whose
horizon fits inside the branch (see train_value.flatten).
"""
from __future__ import annotations

import argparse
import gzip
import json
import queue
import random
import threading
import time
from pathlib import Path

from .agents import MonteCarloAgent, x_range
from .bridge import Engine
from .collect import _round_state, load_games


def pick_boards(paths, count: int, seed: int, min_turn: int = 10):
    """Sample (game, step index) pairs uniformly over all recorded boards."""
    rng = random.Random(seed)
    seen, boards = set(), []
    for p in paths:
        for g in load_games(p, seen):
            for i, st in enumerate(g["steps"]):
                if i >= min_turn:
                    boards.append((g["seed"], g.get("hz", 60), i, st["s"]))
    rng.shuffle(boards)
    return boards[:count]


def run_branch(engine: Engine, board, length: int, seed: int, hz: int, n: int):
    g = engine.load_game(board, seed=seed, hz=hz)
    rng = random.Random(seed)
    lo, hi = x_range(engine.info["radius"], g.state.current)
    g.turn(rng.uniform(lo, hi))             # the random move
    agent = MonteCarloAgent(engine.info["radius"], n=n, seed=seed)
    steps = []
    while not g.state.is_over and len(steps) < length:
        x = agent.act(g)
        steps.append({"s": _round_state(g.raw), "x": float(x), "score": g.state.score})
        g.turn(x)
    ended = g.state.is_over
    score = g.state.score
    g.free()
    return {"seed": seed, "agent": "branch-random+mc-combined-1ply-50", "hz": hz, "score": score,
            "turns": len(steps), "ended": ended, "steps": steps}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", nargs="+", required=True, help="recorded games to branch from")
    p.add_argument("--branches", type=int, default=600)
    p.add_argument("--length", type=int, default=40, help="Monte Carlo moves after the random drop")
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--seed", type=int, default=500000, help="first branch seed (future fruits, candidates)")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    boards = pick_boards(args.data, args.branches, args.seed)
    print(f"{len(boards)} boards picked", flush=True)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs: queue.Queue = queue.Queue()
    for k, b in enumerate(boards):
        jobs.put((args.seed + k, b))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    done, lock = [0], threading.Lock()

    def worker(wi: int):
        fp = out / f"{stamp}-w{wi}.jsonl.gz"
        with Engine() as eng, gzip.open(fp, "at") as f:
            while True:
                try:
                    seed, (src_seed, hz, turn, board) = jobs.get_nowait()
                except queue.Empty:
                    return
                r = run_branch(eng, board, args.length, seed, hz, args.n)
                r["from"] = {"seed": src_seed, "turn": turn}
                f.write(json.dumps(r, separators=(",", ":")) + "\n")
                f.flush()
                with lock:
                    done[0] += 1
                    print(json.dumps({"n": done[0], "seed": seed, "from": r["from"], "turns": r["turns"],
                                      "gain": r["score"] - (r["steps"][0]["score"] if r["steps"] else r["score"]),
                                      "ended": r["ended"]}), flush=True)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(args.workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
