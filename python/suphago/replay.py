"""Play one game and save it for the replay viewer (viewer/index.html).

    python -m suphago.replay --agent mc --plies 2 --seed 0 --out ../replays/mc2_seed0.json
    python -m suphago.replay --agent value --model ../runs/value_mc2.pt --seed 0 --out ../replays/value_seed0.json

Positions are recorded from the engine frame by frame (not re-simulated in the
browser), because the browser's Math.sin/cos differ from Node's in the last bits
and a re-simulation would drift into a different game.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .bench import make_agent
from .bridge import Engine


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--agent", default="mc", choices=["random", "typematch", "mc", "value", "mcv", "ps"])
    p.add_argument("--policy", default=None, help="ps: policy network checkpoint")
    p.add_argument("--k1", type=int, default=10)
    p.add_argument("--k2", type=int, default=6)
    p.add_argument("--alpha", type=float, default=1.0, help="mcv")
    p.add_argument("--pair", type=float, default=0.0, help="mc/mcv big pair bonus")
    p.add_argument("--wm", type=float, default=0.0, help="mc/mcv big merge bonus")
    p.add_argument("--mode", default="combined", choices=["random", "steps", "combined"])
    p.add_argument("--plies", type=int, default=1)
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--frames", type=int, default=120)
    p.add_argument("--model", default=None)
    p.add_argument("--device", default="cpu")
    p.add_argument("--risk", type=float, default=0.0)
    p.add_argument("--blend", type=float, default=0.0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--hz", type=int, default=60)
    p.add_argument("--every", type=int, default=2, help="record every N physics frames")
    p.add_argument("--max-turns", type=int, default=100000)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    t0 = time.time()
    with Engine() as eng:
        info = eng.info
        agent = make_agent(args, info["radius"], args.seed)
        g = eng.new_game(seed=args.seed, hz=args.hz)
        moves = []
        while not g.state.is_over and len(moves) < args.max_turns:
            cur, nxt, before = g.state.current, g.state.next, g.state.score
            agent.last = None
            x = agent.act(g)
            gain, frames = g.turn_recorded(x, every=args.every)
            m = {"x": round(x, 2), "fruit": cur, "next": nxt, "scoreBefore": before, "gain": gain, "frames": frames}
            if getattr(agent, "last", None):
                m["candidates"] = {
                    "xs": [round(v, 1) for v in agent.last["xs"]],
                    "scores": [round(v, 2) for v in agent.last["scores"]],
                    "unit": agent.last["unit"],
                }
            moves.append(m)
            if len(moves) % 50 == 0:
                print(f"move {len(moves)}, score {g.state.score}", flush=True)
        g.free()

    out = {
        "version": 1,
        "agent": agent.name,
        "seed": args.seed,
        "hz": args.hz,
        "every": args.every,
        "finalScore": g.state.score,
        "box": {"width": info["width"], "height": info["height"], "left": info["marginX"],
                "right": info["width"] - info["marginX"], "bottom": info["height"] - 16, "dropY": info["dropY"], "lineY": 70},
        "radius": info["radius"],
        "mergeScore": info["mergeScore"],
        "moves": moves,
    }
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, separators=(",", ":")))

    # keep a list of replays next to them so the viewer can offer a picker
    index_path = path.parent / "index.json"
    try:
        index = json.loads(index_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        index = []
    index = [e for e in index if e.get("file") != path.name]
    index.append({"file": path.name, "agent": agent.name, "seed": args.seed, "score": g.state.score, "moves": len(moves)})
    index.sort(key=lambda e: (e["agent"], e["seed"]))
    index_path.write_text(json.dumps(index, indent=1, ensure_ascii=False))
    print(f"{agent.name} seed {args.seed}: score {g.state.score}, {len(moves)} moves, "
          f"{path.stat().st_size / 1e6:.1f} MB, {time.time() - t0:.0f}s -> {path}")


if __name__ == "__main__":
    main()
