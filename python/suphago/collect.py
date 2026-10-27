"""Record games for training.

    python -m suphago.collect --agent mc --games 200 --workers 10 --out ../data/mc1

Writes one gzip JSON-lines file per worker. Each line is one game:
  {"seed", "agent", "hz", "score", "turns",
   "steps": [{"s": <state as the engine reports it>, "x": <drop x>, "score": <score before the drop>}, ...]}
The value target for a step is (final score - step score), computed when loading.
"""
from __future__ import annotations

import argparse
import gzip
import json
import queue
import threading
import time
from pathlib import Path

from .bench import make_agent
from .bridge import Engine


def _round_state(s: dict) -> dict:
    s = dict(s)
    s["fruits"] = [[f[0]] + [round(v, 3) for v in f[1:]] for f in s["fruits"]]
    return s


def record_game(engine: Engine, agent, seed: int, hz: int, max_turns: int) -> dict:
    g = engine.new_game(seed=seed, hz=hz)
    steps = []
    while not g.state.is_over and len(steps) < max_turns:
        x = agent.act(g)
        # x is kept at full precision so a game can be replayed exactly from its seed;
        # states are rounded because they are only used as training input.
        steps.append({"s": _round_state(g.raw), "x": float(x), "score": g.state.score})
        g.turn(x)
    g.free()
    return {"seed": seed, "agent": agent.name, "hz": hz, "score": g.state.score, "turns": len(steps), "steps": steps}


def load_games(path: str | Path):
    """Yield games from every *.jsonl.gz under path (or a single file)."""
    path = Path(path)
    files = sorted(path.glob("*.jsonl.gz")) if path.is_dir() else [path]
    for fp in files:
        with gzip.open(fp, "rt") as f:
            for line in f:
                yield json.loads(line)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--agent", default="mc", choices=["random", "typematch", "mc"])
    p.add_argument("--mode", default="combined", choices=["random", "steps", "combined"])
    p.add_argument("--plies", type=int, default=1)
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--frames", type=int, default=120)
    p.add_argument("--games", type=int, default=100)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--hz", type=int, default=60)
    p.add_argument("--seed", type=int, default=100000, help="first game seed (kept apart from benchmark seeds)")
    p.add_argument("--max-turns", type=int, default=100000)
    p.add_argument("--out", required=True, help="output directory")
    args = p.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs: queue.Queue = queue.Queue()
    for i in range(args.games):
        jobs.put(args.seed + i)
    stamp = time.strftime("%Y%m%d-%H%M%S")

    def worker(wi: int):
        fp = out / f"{stamp}-w{wi}.jsonl.gz"
        with Engine() as eng, gzip.open(fp, "at") as f:
            while True:
                try:
                    seed = jobs.get_nowait()
                except queue.Empty:
                    return
                agent = make_agent(args, eng.info["radius"], seed)
                game = record_game(eng, agent, seed, args.hz, args.max_turns)
                f.write(json.dumps(game, separators=(",", ":")) + "\n")
                f.flush()
                print(json.dumps({k: game[k] for k in ("seed", "agent", "score", "turns")}), flush=True)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(args.workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
