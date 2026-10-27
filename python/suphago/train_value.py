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
    games = []
    for p in paths:
        games.extend(load_games(p))
    return games


def flatten(games):
    xs, ys = [], []
    for g in games:
        for st in g["steps"]:
            xs.append(st["s"])
            ys.append((g["score"] - st["score"]) / VALUE_SCALE)
    return xs, np.asarray(ys, dtype=np.float32)


class StateDataset(Dataset):
    def __init__(self, states, targets, flip: bool):
        self.states, self.targets, self.flip = states, targets, flip

    def __len__(self):
        return len(self.states)

    def __getitem__(self, i):
        board, extra = encode(State.from_json(self.states[i]), RADIUS)
        if self.flip and random.random() < 0.5:
            # the box is symmetric around x = 327: mirror the board and negate x velocity
            board = board[:, :, ::-1].copy()
            board[N_TYPES] *= -1
        return torch.from_numpy(board), torch.from_numpy(extra), torch.tensor(self.targets[i])


def evaluate(model, loader, device):
    model.eval()
    preds, ys = [], []
    with torch.no_grad():
        for b, e, y in loader:
            preds.append(model(b.to(device), e.to(device)).float().cpu())
            ys.append(y)
    p, y = torch.cat(preds).numpy(), torch.cat(ys).numpy()
    mae = float(np.abs(p - y).mean() * VALUE_SCALE)
    corr = float(np.corrcoef(p, y)[0, 1]) if len(y) > 1 else float("nan")
    return mae, corr


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
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    games = load_samples(args.data)
    random.Random(args.seed).shuffle(games)
    n_val = max(1, int(len(games) * args.val_frac))
    val_games, train_games = games[:n_val], games[n_val:]
    tx, ty = flatten(train_games)
    vx, vy = flatten(val_games)
    print(f"games: {len(train_games)} train / {len(val_games)} val, states: {len(tx)} / {len(vx)}")
    print(f"baseline MAE (predict train mean): {np.abs(vy - ty.mean()).mean() * VALUE_SCALE:.1f} points")

    device = pick_device()
    model = ValueNet(width=args.width, blocks=args.blocks).to(device)
    print(f"device {device}, params {sum(p.numel() for p in model.parameters()) / 1e6:.2f}M")

    kw = dict(batch_size=args.batch, num_workers=args.loader_workers, persistent_workers=args.loader_workers > 0)
    train_loader = DataLoader(StateDataset(tx, ty, flip=True), shuffle=True, drop_last=True, **kw)
    val_loader = DataLoader(StateDataset(vx, vy, flip=False), shuffle=False, **kw)

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    total = args.epochs * len(train_loader)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=max(total, 1), pct_start=0.1)
    loss_fn = torch.nn.SmoothL1Loss()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    best = math.inf
    log = []
    for ep in range(1, args.epochs + 1):
        model.train()
        t0, tot, n = time.time(), 0.0, 0
        for b, e, y in train_loader:
            b, e, y = b.to(device), e.to(device), y.to(device)
            loss = loss_fn(model(b, e), y)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            tot += loss.item() * len(y)
            n += len(y)
        mae, corr = evaluate(model, val_loader, device)
        row = {"epoch": ep, "train_loss": tot / max(n, 1), "val_mae": mae, "val_corr": corr, "sec": round(time.time() - t0, 1)}
        log.append(row)
        print(json.dumps(row), flush=True)
        if mae < best:
            best = mae
            save(model, out, {"epoch": ep, "val_mae": mae, "val_corr": corr, "data": args.data})
    out.with_suffix(".log.json").write_text(json.dumps(log, indent=1))
    print(f"best val MAE {best:.1f} points -> {out}")


if __name__ == "__main__":
    main()
