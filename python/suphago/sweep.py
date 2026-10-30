"""Run several Monte Carlo settings on the same seeds through one shared job queue.

    python -m suphago.sweep --configs "1:25:1" "1:100:1" "2:100:1" --seeds 0 49 --workers 64 --out sweep.jsonl

Each config is plies:n:s2 (s2 = random second drops per first drop, 2-ply only).
Jobs are (config, seed) pairs, biggest first, so a slow config does not leave
workers idle at the end. Results already in --out are skipped, so a stopped run can
be started again. Every line is a bench result plus "config".
"""
from __future__ import annotations

import argparse
import json
import queue
import threading
import time
from pathlib import Path

from .agents import MonteCarloAgent
from .bench import play
from .bridge import Engine


def cost(plies: int, n: int, s2: int) -> float:
    """Simulations per move, in units of one 120-frame look-ahead."""
    return n if plies == 1 else n * s2 * 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="+", required=True, help="plies:n:s2, e.g. 2:50:3")
    ap.add_argument("--seeds", type=int, nargs=2, default=[0, 49], help="first and last seed (inclusive)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--hz", type=int, default=60)
    ap.add_argument("--wait", type=int, default=0, help="extra frames before each next drop (see bench --wait)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    configs = []
    for c in args.configs:
        plies, n, s2 = (int(v) for v in c.split(":"))
        configs.append((c, plies, n, s2))
    out = Path(args.out)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            try:
                r = json.loads(line)
                done.add((r["config"], r["seed"]))
            except (json.JSONDecodeError, KeyError):
                pass
    jobs = [(cost(p, n, s2), c, p, n, s2, seed)
            for c, p, n, s2 in configs for seed in range(args.seeds[0], args.seeds[1] + 1)
            if (c, seed) not in done]
    jobs.sort(key=lambda j: -j[0])
    print(f"{len(jobs)} games to play ({len(done)} already done)", flush=True)
    q: queue.Queue = queue.Queue()
    for j in jobs:
        q.put(j)
    lock = threading.Lock()
    t0 = time.time()
    count = [0]

    def worker():
        with Engine() as eng:
            radius = eng.info["radius"]
            while True:
                try:
                    _, c, p, n, s2, seed = q.get_nowait()
                except queue.Empty:
                    return
                agent = MonteCarloAgent(radius, n=n, plies=p, s2=s2, seed=seed)
                r = play(eng, agent, seed, args.hz, 100000, args.wait)
                r["agent"], r["config"], r["wait"] = agent.name, c, args.wait
                with lock:
                    count[0] += 1
                    with open(out, "a") as f:
                        f.write(json.dumps(r) + "\n")
                    print(json.dumps({**r, "n_done": count[0], "of": len(jobs),
                                      "elapsed_min": round((time.time() - t0) / 60, 1)}), flush=True)

    threads = [threading.Thread(target=worker) for _ in range(args.workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print("sweep finished", flush=True)


if __name__ == "__main__":
    main()
