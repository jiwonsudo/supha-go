"""What separates long games from the rest: watermelon clears.

    python -m suphago.analyze --data ../data/mc1 ../data/mc2

Two watermelons that touch merge and both disappear (+66). This prints, per agent, how
many games made a watermelon, how many cleared one that way, and how long games lasted
with and without a clear.
"""
from __future__ import annotations

import argparse
import math
import statistics as st
from collections import defaultdict

from .collect import load_games

RADIUS = [r * 0.75 for r in [24.5, 31.5, 44, 48, 61, 78, 91, 111.5, 125.5, 154.5, 180]]
AREA = (599 - 55) * 708


def fill(state) -> float:
    return sum(math.pi * RADIUS[f[0]] ** 2 for f in state["fruits"]) / AREA


def game_row(g):
    steps = g["steps"]
    w = [sum(1 for f in s["s"]["fruits"] if f[0] == 10) for s in steps]
    first = next((i for i, c in enumerate(w) if c), None)
    clears = [i for i in range(1, len(steps)) if w[i] < w[i - 1]]
    c0 = clears[0] if clears else None
    return {
        "agent": g["agent"], "score": g["score"], "turns": len(steps), "first_wm": first, "clears": len(clears),
        "first_clear": c0,
        "fill_before": fill(steps[c0 - 1]["s"]) if c0 else None,
        "fill_after": fill(steps[c0 + 1]["s"]) if c0 and c0 + 1 < len(steps) else None,
    }


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), 2) if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="+", required=True)
    args = ap.parse_args()
    seen, rows = set(), []
    for p in args.data:
        rows += [game_row(g) for g in load_games(p, seen)]
    by = defaultdict(list)
    for r in rows:
        by[r["agent"]].append(r)
    for agent, rs in sorted(by.items()):
        cl = [r for r in rs if r["clears"]]
        no = [r for r in rs if not r["clears"]]
        print(f"{agent}: {len(rs)} games")
        print(f"  made a watermelon {sum(r['first_wm'] is not None for r in rs)}, cleared one {len(cl)}")
        print(f"  without clear: median {med([r['score'] for r in no])} points, {med([r['turns'] for r in no])} turns, "
              f"max {max((r['turns'] for r in no), default=0)} turns")
        if cl:
            print(f"  with clear:    median {med([r['score'] for r in cl])} points, {med([r['turns'] for r in cl])} turns, "
                  f"first clear at turn {med([r['first_clear'] for r in cl])}, "
                  f"fill {med([r['fill_before'] for r in cl])} -> {med([r['fill_after'] for r in cl])}")


if __name__ == "__main__":
    main()
