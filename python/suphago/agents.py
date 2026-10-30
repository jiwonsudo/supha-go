"""Baseline agents, following the setups in Poelsma (2025), "Creating an AI that plays Suika game".

Every agent returns the x coordinate to drop the current fruit at.
"""
from __future__ import annotations

import math
import random

from .bridge import Game

WALL_L, WALL_R = 55.0, 599.0
GAME_OVER_PENALTY = -1000.0


def x_range(radius: list[float], t: int) -> tuple[float, float]:
    return WALL_L + radius[t], WALL_R - radius[t]


def first_hit(game: Game, radius: list[float], x: float):
    """Fruit that a fruit dropped straight down at x would hit first (ignores bounces)."""
    rc = radius[game.state.current]
    best, best_y = None, math.inf
    for f in game.state.fruits:
        reach = rc + radius[f.type]
        dx = abs(f.x - x)
        if dx >= reach:
            continue
        y = f.y - math.sqrt(reach * reach - dx * dx)
        if y < best_y:
            best, best_y = f, y
    return best


def reachable_matches(game: Game, radius: list[float]) -> list[float]:
    """x positions of same-type fruits that can be hit from above."""
    lo, hi = x_range(radius, game.state.current)
    xs = []
    for f in game.state.fruits:
        if f.type != game.state.current:
            continue
        x = min(max(f.x, lo), hi)
        if first_hit(game, radius, x) is f:
            xs.append(x)
    return xs


class RandomAgent:
    name = "random"

    def __init__(self, radius, seed=0):
        self.radius = radius
        self.rng = random.Random(seed)

    def act(self, game: Game) -> float:
        lo, hi = x_range(self.radius, game.state.current)
        return self.rng.uniform(lo, hi)


class TypeMatchAgent:
    """Drop on a random reachable fruit of the same type, else at random."""

    name = "typematch"

    def __init__(self, radius, seed=0):
        self.radius = radius
        self.rng = random.Random(seed)

    def act(self, game: Game) -> float:
        xs = reachable_matches(game, self.radius)
        if xs:
            return self.rng.choice(xs)
        lo, hi = x_range(self.radius, game.state.current)
        return self.rng.uniform(lo, hi)


def heuristic(r: dict) -> float:
    """Evaluation from the paper: +3 per removed fruit, +1 if the pile did not grow,
    +1 per touching fruit of the next type."""
    if r["isOver"]:
        return GAME_OVER_PENALTY
    v = 3 * r["removed"] + (1 if r["topAfter"] >= r["topBefore"] else 0) + r["touchNext"]
    s = r.get("second")
    if s is not None:
        if s["isOver"]:
            return GAME_OVER_PENALTY
        v += 3 * s["removed"] + (1 if s["topAfter"] >= r["topAfter"] else 0)
    return v


# Long games are exactly the ones that clear two watermelons (docs/experiments.md 3-4),
# but the heuristic above never rewards building toward that. These optional terms do.
MERGE_BONUS = {8: 0.5, 9: 2.0, 10: 8.0}   # merging two of type t: 8+8 -> melon, 9+9 -> watermelon, 10+10 -> clear
PAIR_BONUS = {8: 0.5, 9: 1.0, 10: 2.0}    # two of type t close together, ready to merge
PAIR_RANGE = 200.0                        # px of gap at which the pair bonus reaches 0


def big_bonus(r: dict, radius, pair: float, wm: float) -> float:
    """Bonus for big merges during the look-ahead and for big same-type pairs left close."""
    if r["isOver"]:
        return 0.0
    end = r
    v = 0.0
    for part in (r, r.get("second")):
        if part is None:
            continue
        if part.get("isOver"):
            return 0.0
        m = part.get("merged")
        if m and wm:
            v += wm * sum(b * m[t] for t, b in MERGE_BONUS.items())
        if "state" in part:
            end = part
    st = end.get("state")
    if pair and st is not None:
        for t, b in PAIR_BONUS.items():
            fs = [f for f in st.fruits if f.type == t]
            if len(fs) < 2:
                continue
            gap = min(math.hypot(a.x - c.x, a.y - c.y) for i, a in enumerate(fs) for c in fs[i + 1:]) - 2 * radius[t]
            v += pair * b * max(0.0, 1.0 - max(gap, 0.0) / PAIR_RANGE)
    return v


def shape_bonus(r: dict, radius, chain: float, inv: float) -> float:
    """Board-shape terms that experiment 9 found related to how a game goes, on the board
    at the end of the look-ahead: +chain per pair of touching fruits one size apart
    (type 4 and up), -inv per fruit sitting on top of a fruit two or more sizes smaller."""
    if not (chain or inv) or r["isOver"]:
        return 0.0
    end = r
    s = r.get("second")
    if s is not None:
        if s.get("isOver"):
            return 0.0
        if "state" in s:
            end = s
    st = end.get("state")
    if st is None:
        return 0.0
    fs = st.fruits
    links = flips = 0
    for a in fs:
        for b in fs:
            if a is b:
                continue
            if chain and b.type == a.type + 1 and a.type >= 4:
                if math.hypot(a.x - b.x, a.y - b.y) - radius[a.type] - radius[b.type] < 15:
                    links += 1
            if inv and b.y < a.y and b.type > a.type + 1 and abs(b.x - a.x) < radius[a.type] + radius[b.type] * 0.5:
                flips += 1
    return chain * links - inv * flips


class MonteCarloAgent:
    """Simulate candidate drops and pick the best by the heuristic.

    mode: "random" (uniform candidates), "steps" (evenly spaced), or
    "combined" (same-type positions first, filled up with random ones).
    plies: 1 or 2 (second ply drops the known next fruit at one random x).
    """

    def __init__(self, radius, n=50, mode="combined", plies=1, frames=120, seed=0, pair=0.0, wm=0.0, s2=1, chain=0.0, inv=0.0):
        self.radius, self.n, self.mode, self.plies, self.frames = radius, n, mode, plies, frames
        self.pair, self.wm = pair, wm
        self.chain, self.inv = chain, inv   # board-shape terms (shape_bonus)
        self.s2 = s2   # 2-ply: random second drops tried per first drop (the best one counts)
        self.rng = random.Random(seed)
        tag = "".join([f"-s{s2}" if s2 > 1 else "", f"-p{pair:g}" if pair else "", f"-w{wm:g}" if wm else "",
                       f"-c{chain:g}" if chain else "", f"-i{inv:g}" if inv else ""])
        self.name = f"mc-{mode}-{plies}ply-{n}{tag}"

    def candidates(self, game: Game) -> list[float]:
        lo, hi = x_range(self.radius, game.state.current)
        if self.mode == "steps":
            return [lo + (hi - lo) * i / (self.n - 1) for i in range(self.n)]
        xs = reachable_matches(game, self.radius)[: self.n] if self.mode == "combined" else []
        while len(xs) < self.n:
            xs.append(self.rng.uniform(lo, hi))
        return xs

    def second_candidates(self, game: Game, k: int) -> list[float]:
        lo2, hi2 = x_range(self.radius, game.state.next)
        return [self.rng.uniform(lo2, hi2) for _ in range(k)]

    def act(self, game: Game) -> float:
        xs = self.candidates(game)
        second = None
        k = self.s2 if self.plies == 2 else 1
        firsts = [x for x in xs for _ in range(k)]
        if self.plies == 2:
            second = self.second_candidates(game, len(firsts))
        results = game.evaluate(firsts, frames=self.frames, second_xs=second, with_state=bool(self.pair or self.chain or self.inv))
        flat = [heuristic(r) + big_bonus(r, self.radius, self.pair, self.wm)
                + shape_bonus(r, self.radius, self.chain, self.inv) for r in results]
        scores = [max(flat[i * k:(i + 1) * k]) for i in range(len(xs))]
        best = max(scores)
        # kept for the replay viewer; does not affect the choice
        self.last = {"xs": xs, "scores": scores, "unit": "heuristic"}
        return self.rng.choice([x for x, s in zip(xs, scores) if s == best])
