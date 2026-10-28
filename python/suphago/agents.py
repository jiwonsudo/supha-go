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


class MonteCarloAgent:
    """Simulate candidate drops and pick the best by the heuristic.

    mode: "random" (uniform candidates), "steps" (evenly spaced), or
    "combined" (same-type positions first, filled up with random ones).
    plies: 1 or 2 (second ply drops the known next fruit at one random x).
    """

    def __init__(self, radius, n=50, mode="combined", plies=1, frames=120, seed=0):
        self.radius, self.n, self.mode, self.plies, self.frames = radius, n, mode, plies, frames
        self.rng = random.Random(seed)
        self.name = f"mc-{mode}-{plies}ply-{n}"

    def candidates(self, game: Game) -> list[float]:
        lo, hi = x_range(self.radius, game.state.current)
        if self.mode == "steps":
            return [lo + (hi - lo) * i / (self.n - 1) for i in range(self.n)]
        xs = reachable_matches(game, self.radius)[: self.n] if self.mode == "combined" else []
        while len(xs) < self.n:
            xs.append(self.rng.uniform(lo, hi))
        return xs

    def act(self, game: Game) -> float:
        xs = self.candidates(game)
        second = None
        if self.plies == 2:
            lo2, hi2 = x_range(self.radius, game.state.next)
            second = [self.rng.uniform(lo2, hi2) for _ in xs]
        results = game.evaluate(xs, frames=self.frames, second_xs=second)
        scores = [heuristic(r) for r in results]
        best = max(scores)
        # kept for the replay viewer; does not affect the choice
        self.last = {"xs": xs, "scores": scores, "unit": "heuristic"}
        return self.rng.choice([x for x, s in zip(xs, scores) if s == best])
