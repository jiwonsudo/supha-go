"""Play N games with one agent in parallel and report median / IQR.

    python -m suphago.bench --agent random --games 30 --workers 8
    python -m suphago.bench --agent mc --mode combined --plies 2 --games 30 --workers 10
"""
from __future__ import annotations

import argparse
import json
import queue
import statistics
import threading
import time
from pathlib import Path

from .agents import MonteCarloAgent, RandomAgent, TypeMatchAgent
from .bridge import Engine


def make_agent(args, radius, seed):
    if args.agent == "random":
        return RandomAgent(radius, seed)
    if args.agent == "typematch":
        return TypeMatchAgent(radius, seed)
    if args.agent == "mc":
        return MonteCarloAgent(radius, n=args.n, mode=args.mode, plies=args.plies, frames=args.frames, seed=seed)
    raise SystemExit(f"unknown agent {args.agent}")


def play(engine: Engine, agent, seed: int, hz: int, max_turns: int):
    g = engine.new_game(seed=seed, hz=hz)
    turns = 0
    t0 = time.time()
    while not g.state.is_over and turns < max_turns:
        g.turn(agent.act(g))
        turns += 1
    g.free()
    return {"seed": seed, "score": g.state.score, "turns": turns, "sec": round(time.time() - t0, 1),
            "maxFruit": max((f.type for f in g.state.fruits), default=-1)}


def quantile(xs, q):
    xs = sorted(xs)
    i = (len(xs) - 1) * q
    lo, hi = int(i), min(int(i) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--agent", default="random", choices=["random", "typematch", "mc"])
    p.add_argument("--mode", default="combined", choices=["random", "steps", "combined"])
    p.add_argument("--plies", type=int, default=1)
    p.add_argument("--n", type=int, default=50, help="candidates per move (mc)")
    p.add_argument("--frames", type=int, default=120, help="frames simulated after each candidate drop (mc)")
    p.add_argument("--games", type=int, default=30)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--hz", type=int, default=60)
    p.add_argument("--seed", type=int, default=0, help="first game seed")
    p.add_argument("--max-turns", type=int, default=100000)
    p.add_argument("--out", default=None, help="append per-game results (jsonl)")
    args = p.parse_args()

    jobs: queue.Queue = queue.Queue()
    for i in range(args.games):
        jobs.put(args.seed + i)
    results, lock = [], threading.Lock()

    def worker():
        with Engine() as eng:
            while True:
                try:
                    seed = jobs.get_nowait()
                except queue.Empty:
                    return
                agent = make_agent(args, eng.info["radius"], seed)
                r = play(eng, agent, seed, args.hz, args.max_turns)
                r["agent"] = agent.name
                with lock:
                    results.append(r)
                    print(json.dumps(r), flush=True)
                    if args.out:
                        with open(args.out, "a") as f:
                            f.write(json.dumps(r) + "\n")

    t0 = time.time()
    threads = [threading.Thread(target=worker) for _ in range(args.workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    scores = [r["score"] for r in results]
    print(
        f"\n{results[0]['agent']}: {len(scores)} games, median {statistics.median(scores):.0f}, "
        f"p25 {quantile(scores, .25):.0f}, p75 {quantile(scores, .75):.0f}, "
        f"mean turns {statistics.mean(r['turns'] for r in results):.0f}, wall {time.time() - t0:.0f}s"
    )


if __name__ == "__main__":
    main()
