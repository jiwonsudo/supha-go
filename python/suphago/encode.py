"""Turn a game state into neural-network input.

Board: the inside of the box (x 55..599, y 0..708) rasterized on an 8px grid
-> 89 rows x 68 columns. Channels:
  0..10  coverage of each fruit type (0..1, 2x2 supersampled per cell)
  11, 12 x / y velocity of the fruit covering the cell, in px per frame / 10
Extra vector (10): one-hot of the current fruit (5) and the next fruit (5).

Radii come from the engine, so this module needs no engine constants of its own
except the box geometry.
"""
from __future__ import annotations

import numpy as np

from .bridge import State

BOX_X0, BOX_X1 = 55.0, 599.0
BOX_Y0, BOX_Y1 = 0.0, 708.0
CELL = 8.0
W = int(round((BOX_X1 - BOX_X0) / CELL))          # 68
H = int(np.ceil((BOX_Y1 - BOX_Y0) / CELL))        # 89
N_TYPES = 11
N_CHANNELS = N_TYPES + 2
N_EXTRA = 10
VEL_SCALE = 0.1

# 2x2 sample points inside each cell
_SUB = (np.array([0.25, 0.75]) * CELL)


def encode(state: State, radius: list[float]) -> tuple[np.ndarray, np.ndarray]:
    board = np.zeros((N_CHANNELS, H, W), dtype=np.float32)
    for f in state.fruits:
        r = radius[f.type]
        cx, cy = f.x - BOX_X0, f.y - BOX_Y0
        c0 = max(int((cx - r) // CELL), 0)
        c1 = min(int((cx + r) // CELL), W - 1)
        r0 = max(int((cy - r) // CELL), 0)
        r1 = min(int((cy + r) // CELL), H - 1)
        if c0 > c1 or r0 > r1:
            continue
        cols = np.arange(c0, c1 + 1)
        rows = np.arange(r0, r1 + 1)
        # sample point coordinates: (rows, 2) and (cols, 2)
        sx = cols[:, None] * CELL + _SUB[None, :]
        sy = rows[:, None] * CELL + _SUB[None, :]
        dx2 = (sx - cx) ** 2                     # (C, 2)
        dy2 = (sy - cy) ** 2                     # (R, 2)
        inside = (dy2[:, None, :, None] + dx2[None, :, None, :]) <= r * r   # (R, C, 2, 2)
        cov = inside.mean(axis=(2, 3), dtype=np.float32)
        sl = (slice(r0, r1 + 1), slice(c0, c1 + 1))
        board[f.type][sl] = np.maximum(board[f.type][sl], cov)
        m = cov > 0
        board[N_TYPES][sl][m] = f.vx * VEL_SCALE
        board[N_TYPES + 1][sl][m] = f.vy * VEL_SCALE
    extra = np.zeros(N_EXTRA, dtype=np.float32)
    extra[state.current] = 1.0
    extra[5 + state.next] = 1.0
    return board, extra


def to_ascii(board: np.ndarray, step: int = 2) -> str:
    """Rough text picture of the board for eyeballing: digit = dominant fruit type (a = 10)."""
    types = board[:N_TYPES]
    lines = []
    for y in range(0, H, step):
        row = []
        for x in range(0, W, step):
            v = types[:, y, x]
            t = int(v.argmax())
            row.append("." if v[t] < 0.5 else "0123456789a"[t])
        lines.append("".join(row))
    return "\n".join(lines)
