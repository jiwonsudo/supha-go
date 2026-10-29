"""Train the policy network: board -> where the Monte Carlo player dropped.

    python -m suphago.train_policy --data ../data/mc1 ../data/mc2 --epochs 10 --out ../runs/policy_v1.pt

The box is split into 68 columns of 8px (the same grid as the board encoding). The
target is the column of the recorded drop, softened over neighbouring columns because
the Monte Carlo player picks at random among tied candidates. Columns the current fruit
cannot reach (too close to a wall) are masked out.

The next fruit is hidden in a quarter of the samples, so the network also works on
boards two drops ahead, where the next fruit is not known yet.
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
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

from .bridge import State
from .encode import BOX_X0, BOX_X1, CELL, N_TYPES, W, encode
from .model import PolicyNet, pick_device, save
from .train_value import RADIUS, load_samples

N_BINS = W  # 68


def bin_of(x: float) -> int:
    return min(max(int((x - BOX_X0) // CELL), 0), N_BINS - 1)


def bin_center(b: int) -> float:
    return BOX_X0 + (b + 0.5) * CELL


def valid_mask(fruit_type: int, radius) -> np.ndarray:
    """True for columns whose centre the fruit can be dropped at."""
    r = radius[fruit_type]
    c = BOX_X0 + (np.arange(N_BINS) + 0.5) * CELL
    m = (c >= BOX_X0 + r) & (c <= BOX_X1 - r)
    if not m.any():
        m[N_BINS // 2] = True
    return m


def soft_target(b: int, sigma: float) -> np.ndarray:
    d = np.arange(N_BINS) - b
    t = np.exp(-0.5 * (d / sigma) ** 2)
    return (t / t.sum()).astype(np.float32)


def flatten(games):
    xs, bins = [], []
    for g in games:
        for st in g["steps"]:
            xs.append(st["s"])
            bins.append(bin_of(st["x"]))
    return xs, np.asarray(bins, dtype=np.int64)


class MoveDataset(Dataset):
    def __init__(self, states, bins, train: bool, sigma: float, hide_next: float):
        self.states, self.bins, self.train = states, bins, train
        self.sigma, self.hide_next = sigma, hide_next

    def __len__(self):
        return len(self.states)

    def __getitem__(self, i):
        s = State.from_json(self.states[i])
        board, extra = encode(s, RADIUS)
        b = int(self.bins[i])
        mask = valid_mask(s.current, RADIUS)
        if self.train and random.random() < 0.5:
            # mirror: the box is symmetric, so the drop column mirrors too
            board = board[:, :, ::-1].copy()
            board[N_TYPES] *= -1
            b = N_BINS - 1 - b
            mask = mask[::-1].copy()
        if self.train and random.random() < self.hide_next:
            extra[5:] = 0.0
        return (torch.from_numpy(board), torch.from_numpy(extra), torch.tensor(b),
                torch.from_numpy(soft_target(b, self.sigma)), torch.from_numpy(mask))


def masked_logits(logits, mask):
    return logits.masked_fill(~mask, -1e4)


def evaluate(model, loader, device):
    model.eval()
    n, loss, near1, top = 0, 0.0, 0, {5: 0, 10: 0}
    with torch.no_grad():
        for board, extra, b, t, mask in loader:
            board, extra, b, t, mask = board.to(device), extra.to(device), b.to(device), t.to(device), mask.to(device)
            lg = masked_logits(model(board, extra), mask)
            loss += float(-(t * F.log_softmax(lg, dim=1)).sum(1).sum())
            am = lg.argmax(1)
            near1 += int(((am - b).abs() <= 1).sum())
            for k in top:
                tk = lg.topk(k, dim=1).indices
                top[k] += int((tk == b[:, None]).any(1).sum())
            n += len(b)
    return {"val_loss": loss / n, "val_top1_within1": near1 / n,
            "val_recall5": top[5] / n, "val_recall10": top[10] / n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="+", required=True)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--wd", type=float, default=1e-3)
    ap.add_argument("--width", type=int, default=48)
    ap.add_argument("--blocks", type=int, default=2)
    ap.add_argument("--sigma", type=float, default=1.0, help="target spread in columns")
    ap.add_argument("--hide-next", type=float, default=0.25)
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--loader-workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    games = [g for g in load_samples(args.data) if "from" not in g]   # branch games hold random moves
    keys = sorted({g["seed"] for g in games})
    random.Random(args.seed).shuffle(keys)
    val_keys = set(keys[: max(1, int(len(keys) * args.val_frac))])
    tr = [g for g in games if g["seed"] not in val_keys]
    va = [g for g in games if g["seed"] in val_keys]
    tx, tb = flatten(tr)
    vx, vb = flatten(va)
    print(f"games: {len(tr)} train / {len(va)} val, moves: {len(tx)} / {len(vx)}", flush=True)

    device = pick_device()
    model = PolicyNet(width=args.width, blocks=args.blocks).to(device)
    print(f"device {device}, params {sum(p.numel() for p in model.parameters()) / 1e6:.2f}M", flush=True)
    kw = dict(batch_size=args.batch, num_workers=args.loader_workers, persistent_workers=args.loader_workers > 0)
    train_loader = DataLoader(MoveDataset(tx, tb, True, args.sigma, args.hide_next), shuffle=True, drop_last=True, **kw)
    val_loader = DataLoader(MoveDataset(vx, vb, False, args.sigma, 0.0), shuffle=False, **kw)

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.wd)
    total = args.epochs * len(train_loader)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=max(total, 1), pct_start=0.1)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    best, log = math.inf, []
    for ep in range(1, args.epochs + 1):
        model.train()
        t0, tot, n = time.time(), 0.0, 0
        for board, extra, b, t, mask in train_loader:
            board, extra, t, mask = board.to(device), extra.to(device), t.to(device), mask.to(device)
            lg = masked_logits(model(board, extra), mask)
            loss = -(t * F.log_softmax(lg, dim=1)).sum(1).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            tot += loss.item() * len(t)
            n += len(t)
        ev = evaluate(model, val_loader, device)
        row = {"epoch": ep, "train_loss": tot / max(n, 1), **ev, "sec": round(time.time() - t0, 1)}
        log.append(row)
        print(json.dumps(row), flush=True)
        if ev["val_loss"] < best:
            best = ev["val_loss"]
            save(model, out, {"epoch": ep, **ev, "data": args.data})
    out.with_suffix(".log.json").write_text(json.dumps(log, indent=1))
    print(f"best val loss {best:.3f} -> {out}")


if __name__ == "__main__":
    main()
