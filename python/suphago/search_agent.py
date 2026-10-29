"""Policy-guided 2-ply search ("ps" agent).

The Monte Carlo 2-ply baseline tries 50 first drops and, for each, ONE random second
drop. This agent spends about the same simulation budget differently:

  1. the policy network proposes k1 first drops (plus drops on top of same-type fruits);
  2. each is played to the next decision point as an exact copy of the game (children);
  3. the policy proposes k2 second drops on each copy (next-next fruit unknown -> hidden);
  4. every second drop is simulated 120 frames and scored by the heuristic, plus the
     value network on the final board (alpha, risk as in MCValueAgent);
  5. a first drop is worth  heuristic(first) + best over its second drops.

So the second ply is a real choice (max over replies) instead of one random sample.
"""
from __future__ import annotations

import random

import numpy as np
import torch

from .agents import GAME_OVER_PENALTY, MonteCarloAgent, heuristic, reachable_matches, x_range
from .bridge import Game
from .encode import encode
from .model import VALUE_SCALE, load
from .train_policy import bin_center, valid_mask


def first_heuristic(r: dict) -> float:
    """Heuristic counts of the first drop, measured at the next decision point."""
    if r["isOver"]:
        return GAME_OVER_PENALTY
    return 3 * r["removed"] + (1 if r["topAfter"] >= r["topBefore"] else 0) + r["touchNext"]


class PolicySearchAgent:
    def __init__(self, radius, policy_path, value_path=None, k1=10, k2=6, frames=120, device="cpu",
                 seed=0, alpha=1.0, risk=1.0, matches=3):
        self.radius = radius
        self.device = torch.device(device)
        if self.device.type == "cpu":
            torch.set_num_threads(1)
        self.policy = load(policy_path, self.device)
        self.value = None
        if value_path:
            from .value_agent import ValueAgent
            self._v = ValueAgent(radius, value_path, device=device, seed=seed)
            self.value = self._v.model
        self.k1, self.k2, self.frames = k1, k2, frames
        self.alpha, self.risk, self.matches = alpha, risk, matches
        self.rng = random.Random(seed)
        v = f"-a{alpha:g}-r{risk:g}" if value_path else ""
        self.name = f"ps-{k1}x{k2}{v}"

    # ---- policy ----
    def propose(self, states, k, hide_next):
        """Top-k drop x for each state (column centres, clipped to the reachable range)."""
        boards, extras, masks = [], [], []
        for s in states:
            b, e = encode(s, self.radius)
            if hide_next:
                e[5:] = 0.0
            boards.append(b)
            extras.append(e)
            masks.append(valid_mask(s.current, self.radius))
        with torch.no_grad():
            lg = self.policy(torch.from_numpy(np.stack(boards)).to(self.device),
                             torch.from_numpy(np.stack(extras)).to(self.device)).float().cpu().numpy()
        lg[~np.stack(masks)] = -1e9
        out = []
        for s, row in zip(states, lg):
            lo, hi = x_range(self.radius, s.current)
            order = np.argsort(-row)[:k]
            out.append([min(max(bin_center(int(b)), lo), hi) for b in order])
        return out

    def act(self, game: Game) -> float:
        root = game.state
        xs1 = self.propose([root], self.k1, hide_next=False)[0]
        # drops right on top of a same-type fruit are cheap, strong candidates
        for x in reachable_matches(game, self.radius)[: self.matches]:
            if all(abs(x - y) > 4 for y in xs1):
                xs1.append(x)
        kids = game.children(xs1)
        scores = np.array([first_heuristic(r) for r in kids], dtype=np.float32)
        alive = [i for i, r in enumerate(kids) if not r["isOver"]]
        if alive:
            props = self.propose([kids[i]["state"] for i in alive], self.k2, hide_next=True)
            leaf_states, leaf_owner, leaf_h = [], [], []
            for i, xs2 in zip(alive, props):
                res = kids[i]["game"].evaluate(xs2, frames=self.frames, with_state=True)
                for r in res:
                    h = heuristic(r)
                    leaf_h.append(h)
                    leaf_owner.append(i)
                    leaf_states.append(r.get("state"))
            leaf_h = np.array(leaf_h, dtype=np.float32)
            if self.value is not None:
                idx = [j for j, s in enumerate(leaf_states) if s is not None and leaf_h[j] > GAME_OVER_PENALTY]
                if idx:
                    v, p = self._v.score_states([leaf_states[j] for j in idx], unknown_current=True)
                    leaf_h[idx] += self.alpha * v * VALUE_SCALE / 100.0 - self.risk * 10.0 * p
            best = {}
            for o, h in zip(leaf_owner, leaf_h):
                best[o] = max(best.get(o, -np.inf), h)
            for i in alive:
                scores[i] += best.get(i, GAME_OVER_PENALTY)
        game.engine.free_many([r["id"] for r in kids])
        top = scores.max()
        self.last = {"xs": list(xs1), "scores": [float(s) for s in scores], "unit": "heuristic"}
        return self.rng.choice([x for x, s in zip(xs1, scores) if s >= top - 1e-9])
