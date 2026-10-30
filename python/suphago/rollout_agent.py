"""Rollout search (--agent ro): judge each move by how the game goes long after it.

1. Monte Carlo 1-ply (the usual 50 candidates, 120 frames, Poelsma heuristic) keeps the
   `top` best drops. Drops that end the game right away are left out.
2. Each kept drop is played out `count` times for up to `length` more moves by a fast
   policy inside the engine (rollout.js), on fresh random fruits. Every candidate sees
   the same `count` fruit sequences, so they are compared on equal luck.
3. Value = mean points gained - death x (share of rollouts that ended the game).
   Ties go to the better heuristic score, then at random.
"""
from __future__ import annotations

import random

from .agents import MonteCarloAgent, heuristic
from .bridge import Game


class RolloutAgent:
    def __init__(self, radius, n=50, top=10, count=8, length=50, policy_k=0, death=1000.0, seed=0):
        self.radius = radius
        self.top, self.count, self.length, self.policy_k, self.death = top, count, length, policy_k, death
        self.rng = random.Random(seed)
        self._cand = MonteCarloAgent(radius, n=n, seed=seed)
        self.name = f"ro-{n}-t{top}-c{count}-l{length}" + (f"-k{policy_k}" if policy_k else "") + f"-d{death:g}"

    def act(self, game: Game) -> float:
        xs = self._cand.candidates(game)
        res = game.evaluate(xs, frames=120)
        h = [heuristic(r) for r in res]
        alive = [i for i in range(len(xs)) if not res[i]["isOver"]]
        if not alive:
            return xs[max(range(len(xs)), key=lambda i: h[i])]
        alive.sort(key=lambda i: (-h[i], self.rng.random()))
        keep = alive[: self.top]
        ro = game.rollout([xs[i] for i in keep], count=self.count, length=self.length,
                          k=self.policy_k, seed=self.rng.randrange(1, 2 ** 30))
        vals = [r["gain"] - self.death * r["over"] for r in ro]
        best = max(range(len(keep)), key=lambda j: (vals[j], h[keep[j]], self.rng.random()))
        self.last = {"xs": [xs[i] for i in keep], "scores": vals, "unit": "rollout"}
        return xs[keep[best]]
