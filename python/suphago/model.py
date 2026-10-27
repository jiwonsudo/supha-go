"""Value network: board -> expected points still to come in this game.

The output is in units of VALUE_SCALE points so the target sits around 0..5.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .encode import N_CHANNELS, N_EXTRA

VALUE_SCALE = 1000.0


class ResBlock(nn.Module):
    def __init__(self, ch: int):
        super().__init__()
        self.c1 = nn.Conv2d(ch, ch, 3, padding=1, bias=False)
        self.b1 = nn.BatchNorm2d(ch)
        self.c2 = nn.Conv2d(ch, ch, 3, padding=1, bias=False)
        self.b2 = nn.BatchNorm2d(ch)

    def forward(self, x):
        y = F.relu(self.b1(self.c1(x)))
        y = self.b2(self.c2(y))
        return F.relu(x + y)


class Down(nn.Module):
    def __init__(self, cin: int, cout: int):
        super().__init__()
        self.c = nn.Conv2d(cin, cout, 3, stride=2, padding=1, bias=False)
        self.b = nn.BatchNorm2d(cout)

    def forward(self, x):
        return F.relu(self.b(self.c(x)))


class ValueNet(nn.Module):
    """89x68 board -> 45x34 -> 23x17 -> 12x9, then pooled and joined with the
    current/next fruit vector."""

    def __init__(self, width: int = 48, blocks: int = 2):
        super().__init__()
        w = width
        self.stem = nn.Sequential(nn.Conv2d(N_CHANNELS, w, 3, padding=1, bias=False), nn.BatchNorm2d(w), nn.ReLU())
        stages = []
        chans = [w, w * 2, w * 2, w * 4]
        for i in range(3):
            stages.append(Down(chans[i], chans[i + 1]))
            stages += [ResBlock(chans[i + 1]) for _ in range(blocks)]
        self.body = nn.Sequential(*stages)
        c = chans[-1]
        self.head = nn.Sequential(
            nn.Linear(c * 2 + N_EXTRA, 256), nn.ReLU(),
            nn.Linear(256, 128), nn.ReLU(),
            nn.Linear(128, 1),
        )
        self.config = {"width": width, "blocks": blocks}

    def forward(self, board: torch.Tensor, extra: torch.Tensor) -> torch.Tensor:
        x = self.body(self.stem(board))
        pooled = torch.cat([x.mean(dim=(2, 3)), x.amax(dim=(2, 3))], dim=1)
        return self.head(torch.cat([pooled, extra], dim=1)).squeeze(1)


def pick_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def save(model: ValueNet, path, meta: dict | None = None):
    torch.save({"config": model.config, "state": model.state_dict(), "meta": meta or {}}, path)


def load(path, device=None) -> ValueNet:
    ck = torch.load(path, map_location="cpu", weights_only=False)
    m = ValueNet(**ck["config"])
    m.load_state_dict(ck["state"])
    m.eval()
    if device is not None:
        m.to(device)
    return m
