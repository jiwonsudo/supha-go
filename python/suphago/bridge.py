"""Python side of the engine bridge.

Each Engine owns one Node worker process (engine/src/server.js) and talks to it
with JSON lines. Run several Engines in threads for parallel games; the GIL is
released while waiting on the pipe.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "engine" / "src" / "server.js"


class EngineError(RuntimeError):
    pass


class Engine:
    def __init__(self, node: str = "node"):
        self.proc = subprocess.Popen(
            [node, str(SERVER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(ROOT / "engine"),
        )
        self.info = self.call("info")

    def call(self, cmd: str, **kw):
        kw["cmd"] = cmd
        self.proc.stdin.write(json.dumps(kw) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise EngineError("engine process exited")
        msg = json.loads(line)
        if not msg["ok"]:
            raise EngineError(msg["error"])
        return msg["result"]

    def new_game(self, seed: int = 0, hz: int = 60) -> "Game":
        r = self.call("new", seed=seed, hz=hz)
        return Game(self, r["id"], r["state"])

    def close(self):
        if self.proc.poll() is None:
            self.proc.stdin.close()
            self.proc.wait(timeout=5)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


@dataclass
class Fruit:
    type: int
    x: float
    y: float
    vx: float
    vy: float
    angle: float
    av: float


@dataclass
class State:
    score: int
    is_over: bool
    current: int
    next: int
    fruits: list[Fruit]

    @staticmethod
    def from_json(d) -> "State":
        return State(d["score"], d["isOver"], d["current"], d["next"], [Fruit(*f) for f in d["fruits"]])


class Game:
    def __init__(self, engine: Engine, gid: int, raw_state: dict):
        self.engine = engine
        self.id = gid
        self._set(raw_state)

    def _set(self, raw_state: dict):
        self.raw = raw_state          # JSON form, as the engine sent it (used for saving games)
        self.state = State.from_json(raw_state)

    def turn(self, x: float, extra: int = 0) -> int:
        r = self.engine.call("turn", id=self.id, x=float(x), extra=extra)
        self._set(r["state"])
        return r["gain"]

    def evaluate(self, xs, frames: int = 120, second_xs=None):
        kw = {"id": self.id, "xs": [float(x) for x in xs], "frames": frames}
        if second_xs is not None:
            kw["secondXs"] = [float(x) for x in second_xs]
        return self.engine.call("evaluate", **kw)

    def expand(self, xs):
        """For each x: drop there and run to the next decision point.
        Returns dicts with gain, isOver and state (State)."""
        out = self.engine.call("expand", id=self.id, xs=[float(x) for x in xs])
        for r in out:
            r["state"] = State.from_json(r["state"])
        return out

    def free(self):
        self.engine.call("free", id=self.id)
