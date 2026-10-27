"""Monte Carlo search scored by the value network instead of the hand-made formula.

For each candidate x: drop there and run to the next decision point, then
    score = points gained + V(resulting state)
A game over scores only the points gained (nothing more to come).

The clone used for the look-ahead has already drawn the fruit after next, which
the real player cannot see. To avoid using that, V is averaged over all 5 possible
values of that fruit.
"""
from __future__ import annotations

import random

import numpy as np
import torch

from .agents import MonteCarloAgent, x_range
from .bridge import Game
from .encode import encode
from .model import VALUE_SCALE, load

SPAWN_TYPES = 5


class ValueAgent:
    def __init__(self, radius, model_path, n=50, mode="combined", device="cpu", seed=0):
        self.radius = radius
        self.device = torch.device(device)
        self.model = load(model_path, self.device)
        self.rng = random.Random(seed)
        # reuse the candidate generator of the baseline so the only difference is the scoring
        self._cand = MonteCarloAgent(radius, n=n, mode=mode, seed=seed)
        self._cand.rng = self.rng
        self.name = f"value-{mode}-{n}"

    def score_states(self, states) -> np.ndarray:
        if not states:
            return np.zeros(0, dtype=np.float32)
        boards, extras = [], []
        for s in states:
            b, e = encode(s, self.radius)
            for nxt in range(SPAWN_TYPES):
                e2 = e.copy()
                e2[5:] = 0.0
                e2[5 + nxt] = 1.0
                boards.append(b)
                extras.append(e2)
        with torch.no_grad():
            v = self.model(torch.from_numpy(np.stack(boards)).to(self.device),
                           torch.from_numpy(np.stack(extras)).to(self.device)).float().cpu().numpy()
        return v.reshape(len(states), SPAWN_TYPES).mean(axis=1)

    def act(self, game: Game) -> float:
        xs = self._cand.candidates(game)
        results = game.expand(xs)
        alive = [i for i, r in enumerate(results) if not r["isOver"]]
        values = np.zeros(len(xs), dtype=np.float32)
        values[alive] = self.score_states([results[i]["state"] for i in alive])
        scores = np.array([r["gain"] / VALUE_SCALE for r in results], dtype=np.float32) + values
        best = scores.max()
        return self.rng.choice([x for x, s in zip(xs, scores) if s >= best - 1e-9])
