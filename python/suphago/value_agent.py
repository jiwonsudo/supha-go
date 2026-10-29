"""Monte Carlo search scored by the value network instead of (or mixed with) the hand-made formula.

For each candidate x: drop there and run to the next decision point, then
    score = points gained + V(resulting state) - risk * P(game ends soon) * 1000 + blend * heuristic
A game over scores only the points gained (nothing more to come) minus the risk term.

The clone used for the look-ahead has already drawn the fruit after next, which
the real player cannot see. To avoid using that, V and P are averaged over all 5
possible values of that fruit.

`heuristic` is the Monte Carlo formula (3 per removed fruit, +1 if the pile did not
grow, +1 per touching fruit of the next type), measured over the same short look-ahead.
"""
from __future__ import annotations

import random

import numpy as np
import torch

from .agents import MonteCarloAgent
from .bridge import Game
from .encode import encode
from .model import VALUE_SCALE, load

SPAWN_TYPES = 5


def short_heuristic(r: dict) -> float:
    return 3 * r["removed"] + (1 if r["topAfter"] >= r["topBefore"] else 0) + r["touchNext"]


class ValueAgent:
    def __init__(self, radius, model_path, n=50, mode="combined", device="cpu", seed=0, risk=0.0, blend=0.0):
        self.radius = radius
        self.device = torch.device(device)
        if self.device.type == "cpu":
            # benchmark workers are threads in one process; one thread each avoids oversubscribing cores
            torch.set_num_threads(1)
        self.model = load(model_path, self.device)
        self.risk, self.blend = risk, blend
        self.rng = random.Random(seed)
        # reuse the candidate generator of the baseline so the only difference is the scoring
        self._cand = MonteCarloAgent(radius, n=n, mode=mode, seed=seed)
        self._cand.rng = self.rng
        tag = "".join([f"-r{risk:g}" if risk else "", f"-b{blend:g}" if blend else ""])
        self.name = f"value-{mode}-{n}{tag}"

    def score_states(self, states, unknown_current: bool = False):
        """Mean value (points / VALUE_SCALE) and mean game-over probability per state.

        The next fruit is always unknown to the player at these states, so it is averaged
        over all 5 spawn types. With unknown_current (states two drops ahead) the current
        fruit is unknown too and both are averaged (25 combinations)."""
        if not states:
            return np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.float32)
        combos = [(c, n) for c in range(SPAWN_TYPES) for n in range(SPAWN_TYPES)] if unknown_current \
            else [(None, n) for n in range(SPAWN_TYPES)]
        k = len(combos)
        boards, extras = [], []
        for s in states:
            b, e = encode(s, self.radius)
            boards.append(b)
            for cur, nxt in combos:
                e2 = e.copy()
                if cur is not None:
                    e2[:5] = 0.0
                    e2[cur] = 1.0
                e2[5:] = 0.0
                e2[5 + nxt] = 1.0
                extras.append(e2)
        with torch.no_grad():
            # the unknown fruits only enter the small head, so run the board once per state
            feats = self.model.features(torch.from_numpy(np.stack(boards)).to(self.device))
            feats = feats.repeat_interleave(k, dim=0)
            v, ol = self.model.head_from(feats, torch.from_numpy(np.stack(extras)).to(self.device))
        v = v.float().cpu().numpy().reshape(len(states), k).mean(axis=1)
        if ol is None:
            p = np.zeros(len(states), dtype=np.float32)
        else:
            p = torch.sigmoid(ol).float().cpu().numpy().reshape(len(states), k).mean(axis=1)
        return v, p

    def act(self, game: Game) -> float:
        xs = self._cand.candidates(game)
        results = game.expand(xs)
        alive = [i for i, r in enumerate(results) if not r["isOver"]]
        values = np.zeros(len(xs), dtype=np.float32)
        overp = np.ones(len(xs), dtype=np.float32)  # a drop that ends the game is certain game over
        v, p = self.score_states([results[i]["state"] for i in alive])
        values[alive] = v
        overp[alive] = p
        gains = np.array([r["gain"] for r in results], dtype=np.float32)
        heur = np.array([short_heuristic(r) for r in results], dtype=np.float32)
        scores = gains + values * VALUE_SCALE - self.risk * overp * VALUE_SCALE + self.blend * heur
        best = scores.max()
        # kept for the replay viewer; does not affect the choice
        self.last = {"xs": xs, "scores": [float(s) for s in scores], "unit": "points"}
        return self.rng.choice([x for x, s in zip(xs, scores) if s >= best - 1e-9])


class MCValueAgent(ValueAgent):
    """The Monte Carlo baseline with the value network as a helper, not a replacement.

    Each candidate is simulated exactly as the baseline does (120 frames, same candidates,
    same heuristic). The value network then scores the board at the end of that
    look-ahead and the game-over head penalizes risky boards:

        score = heuristic + alpha * V(points) / 100 - risk * 10 * P(game over soon)

    With alpha = risk = 0 this is the baseline. alpha = 1 makes 100 predicted points worth
    one heuristic point, so the network mostly breaks the many ties the heuristic leaves.
    """

    def __init__(self, radius, model_path, n=50, mode="combined", device="cpu", seed=0,
                 alpha=1.0, risk=1.0, frames=120, plies=1):
        super().__init__(radius, model_path, n=n, mode=mode, device=device, seed=seed)
        self.alpha, self.risk, self.frames, self.plies = alpha, risk, frames, plies
        self._cand.plies = plies
        ply = f"-{plies}ply" if plies != 1 else ""
        self.name = f"mcv-{mode}{ply}-{n}-a{alpha:g}-r{risk:g}"

    def act(self, game: Game) -> float:
        from .agents import heuristic
        xs = self._cand.candidates(game)
        second = None
        if self.plies == 2:
            # same second-ply sampling as the 2-ply baseline: the known next fruit at one random x
            second = self._cand.second_candidates(game, len(xs))
        results = game.evaluate(xs, frames=self.frames, second_xs=second, with_state=True)
        base = np.array([heuristic(r) for r in results], dtype=np.float32)
        # board to score: after the second drop when there is one
        ends = [r.get("second", {}) if second is not None else r for r in results]
        alive = [i for i, (r, e) in enumerate(zip(results, ends)) if not r["isOver"] and "state" in e]
        v = np.zeros(len(xs), dtype=np.float32)
        p = np.zeros(len(xs), dtype=np.float32)
        if alive and (self.alpha or self.risk):
            vv, pp = self.score_states([ends[i]["state"] for i in alive], unknown_current=second is not None)
            v[alive], p[alive] = vv, pp
        scores = base + self.alpha * v * VALUE_SCALE / 100.0 - self.risk * 10.0 * p
        best = scores.max()
        self.last = {"xs": xs, "scores": [float(s) for s in scores], "unit": "heuristic"}
        return self.rng.choice([x for x, s in zip(xs, scores) if s >= best - 1e-9])
