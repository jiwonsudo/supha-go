"""Train the value network on recorded games.

    python -m suphago.train_value --data ../data/mc1 --epochs 15 --out ../runs/value_mc1.pt

Target for each recorded state: points still to come (final score - score at that state).
Games are split into train / validation by game, so no game appears in both.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from .bridge import State
from .collect import load_games
from .encode import N_TYPES, encode
from .model import VALUE_SCALE, ValueNet, pick_device, save

# Must match engine RADIUS (engine/src/suika.js). Kept here so training needs no Node process.
RADIUS = [r * 0.75 for r in [24.5, 31.5, 44, 48, 61, 78, 91, 111.5, 125.5, 154.5, 180]]


def load_samples(paths: list[str]):
    games, seen = [], set()
    for p in paths:
        games.extend(load_games(p, seen))
    return games


def flatten(games, horizon: int = 0, over_within: int = 15):
    """Value target: points gained over the next `horizon` moves (0 = until the game ends).
    Game-over target: 1 if the game ends within `over_within` moves of this state."""
    xs, ys, os_ = [], [], []
    for g in games:
        steps = g["steps"]
        n = len(steps)
        for i, st in enumerate(steps):
            j = i + horizon
            later = steps[j]["score"] if (horizon and j < n) else g["score"]
            xs.append(st["s"])
            ys.append((later - st["score"]) / VALUE_SCALE)
            os_.append(1.0 if n - i <= over_within else 0.0)
    return xs, np.asarray(ys, dtype=np.float32), np.asarray(os_, dtype=np.float32)


class StateDataset(Dataset):
    def __init__(self, states, targets, overs, flip: bool):
        self.states, self.targets, self.overs, self.flip = states, targets, overs, flip

    def __len__(self):
        return len(self.states)

    def __getitem__(self, i):
        board, extra = encode(State.from_json(self.states[i]), RADIUS)
        if self.flip and random.random() < 0.5:
            # the box is symmetric around x = 327: mirror the board and negate x velocity
            board = board[:, :, ::-1].copy()
            board[N_TYPES] *= -1
        return torch.from_numpy(board), torch.from_numpy(extra), torch.tensor(self.targets[i]), torch.tensor(self.overs[i])


def auc(scores, labels):
    """Probability that a random game-ending state scores above a random safe one."""
    pos, neg = scores[labels > 0.5], scores[labels <= 0.5]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    ranks = np.argsort(np.argsort(np.concatenate([pos, neg]))) + 1
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def evaluate(model, loader, device):
    model.eval()
    preds, ys, ologits, os_ = [], [], [], []
    with torch.no_grad():
        for b, e, y, o in loader:
            v, ol = model(b.to(device), e.to(device))
            preds.append(v.float().cpu())
            ys.append(y)
            if ol is not None:
                ologits.append(ol.float().cpu())
                os_.append(o)
    p, y = torch.cat(preds).numpy(), torch.cat(ys).numpy()
    res = {"val_mae": float(np.abs(p - y).mean() * VALUE_SCALE),
           "val_corr": float(np.corrcoef(p, y)[0, 1]) if len(y) > 1 else float("nan")}
    if ologits:
        res["val_over_auc"] = auc(torch.cat(ologits).numpy(), torch.cat(os_).numpy())
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="+", required=True, help="directories or files of recorded games")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--width", type=int, default=48)
    ap.add_argument("--blocks", type=int, default=2)
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--loader-workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--horizon", type=int, default=0, help="value target = points in the next N moves (0 = until game end)")
    ap.add_argument("--over-head", action="store_true", help="also predict whether the game ends soon")
    ap.add_argument("--over-within", type=int, default=15, help="'ends soon' = within this many moves")
    ap.add_argument("--over-weight", type=float, default=0.5)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    games = load_samples(args.data)
    random.Random(args.seed).shuffle(games)
    n_val = max(1, int(len(games) * args.val_frac))
    val_games, train_games = games[:n_val], games[n_val:]
    tx, ty, to = flatten(train_games, args.horizon, args.over_within)
    vx, vy, vo = flatten(val_games, args.horizon, args.over_within)
    print(f"games: {len(train_games)} train / {len(val_games)} val, states: {len(tx)} / {len(vx)}")
    print(f"baseline MAE (predict train mean): {np.abs(vy - ty.mean()).mean() * VALUE_SCALE:.1f} points")

    device = pick_device()
    model = ValueNet(width=args.width, blocks=args.blocks, over_head=args.over_head).to(device)
    print(f"device {device}, params {sum(p.numel() for p in model.parameters()) / 1e6:.2f}M")

    kw = dict(batch_size=args.batch, num_workers=args.loader_workers, persistent_workers=args.loader_workers > 0)
    train_loader = DataLoader(StateDataset(tx, ty, to, flip=True), shuffle=True, drop_last=True, **kw)
    val_loader = DataLoader(StateDataset(vx, vy, vo, flip=False), shuffle=False, **kw)

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    total = args.epochs * len(train_loader)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=max(total, 1), pct_start=0.1)
    loss_fn = torch.nn.SmoothL1Loss()
    bce = torch.nn.BCEWithLogitsLoss()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    best = math.inf
    log = []
    for ep in range(1, args.epochs + 1):
        model.train()
        t0, tot, n = time.time(), 0.0, 0
        for b, e, y, o in train_loader:
            b, e, y, o = b.to(device), e.to(device), y.to(device), o.to(device)
            v, ol = model(b, e)
            loss = loss_fn(v, y)
            if ol is not None:
                loss = loss + args.over_weight * bce(ol, o)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            tot += loss.item() * len(y)
            n += len(y)
        ev = evaluate(model, val_loader, device)
        mae = ev["val_mae"]
        row = {"epoch": ep, "train_loss": tot / max(n, 1), **ev, "sec": round(time.time() - t0, 1)}
        log.append(row)
        print(json.dumps(row), flush=True)
        if mae < best:
            best = mae
            save(model, out, {"epoch": ep, **ev, "data": args.data, "horizon": args.horizon,
                              "over_within": args.over_within})
    out.with_suffix(".log.json").write_text(json.dumps(log, indent=1))
    print(f"best val MAE {best:.1f} points -> {out}")


if __name__ == "__main__":
    main()
