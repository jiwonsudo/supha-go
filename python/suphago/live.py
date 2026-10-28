"""Let an agent play the real game on playsuikagame.com.

    pip install playwright && python3 -m playwright install chromium
    python3 -m suphago.live --agent mc --plies 2
    python3 -m suphago.live --agent value --model ../runs/value_mc2.pt

A Chromium window opens on the site. Close any cookie or ad popups yourself,
then press Enter in the terminal. Each turn the script:
  1. waits until the page lets you drop the next fruit,
  2. pauses the page's physics and reads every fruit (type, position, velocity, spin),
  3. rebuilds that board in our engine and lets the agent choose x,
  4. resumes physics and clicks the canvas at x (a normal mouse click).
Pausing while the agent thinks keeps the board it planned on identical to the board
it drops into. Use --no-pause to play in real time instead (the board keeps moving
while the agent thinks, so its plan is slightly stale).

When the game ends, the page submits the score to its public leaderboard like any game.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from .bench import make_agent
from .bridge import Engine

URL = "https://playsuikagame.com/ko"

READ_JS = r"""
() => {
  if (typeof game === 'undefined' || !game.scene || !game.scene.scenes[0]) return null;
  const s = game.scene.scenes[0];
  const preview = s.children.list.find(o => o.texture && /^fruit\d+$/.test(o.texture.key) && !o.body && o.active && o.y === 80);
  const nextEl = document.getElementById('next-drop');
  const m = nextEl && nextEl.src.match(/sprite\/(\d+)\.png/);
  const list = (typeof fruits !== 'undefined' ? fruits : []).filter(f => f.body && f.active);
  return {
    isOver: typeof isOver !== 'undefined' && !!isOver,
    score: typeof score !== 'undefined' ? score : 0,
    canDrop: !!preview,
    current: preview ? parseInt(preview.texture.key.slice(5)) : null,
    next: m ? parseInt(m[1]) : null,
    fruits: list.map(f => { const b = f.body; return [parseInt(f.texture.key.slice(5)), b.position.x, b.position.y, b.velocity.x, b.velocity.y, b.angle, b.angularVelocity]; }),
  };
}
"""

# Replace the page's fruit picker with the engine's seeded generator (mulberry32,
# same draws in the same order as engine/src/suika.js), so the page deals the same
# fruits as `SuikaGame({seed})`. Installed before the game script runs.
SEED_INIT_JS = r"""
(() => {
  let a = __SEED__ >>> 0;
  const rng = () => { a = (a + 0x6d2b79f5) >>> 0; let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  window.__suphagoDraws = [];
  const seeded = function randomFruit() { const k = Math.floor(rng() * 5); window.__suphagoDraws.push(k); return 'fruit' + k; };
  const swap = () => { if (typeof window.randomFruit === 'function' && window.randomFruit !== seeded) { window.randomFruit = seeded; } };
  const iv = setInterval(swap, 0);
  setTimeout(() => clearInterval(iv), 30000);
  document.addEventListener('DOMContentLoaded', swap);
})();
"""

PAUSE_JS ="() => game.scene.scenes[0].matter.world.pause()"
RESUME_JS = "() => game.scene.scenes[0].matter.world.resume()"

FPS_JS = r"""
() => new Promise(res => { let n = 0; const t0 = performance.now();
  const f = () => { n++; if (performance.now() - t0 < 1000) requestAnimationFrame(f); else res(n); };
  requestAnimationFrame(f); })
"""


def canvas_point(page, x: float):
    """Screen coordinates on the canvas for game x (y is irrelevant for the drop)."""
    box = page.evaluate("() => { const r = game.canvas.getBoundingClientRect(); return [r.left, r.top, r.width, r.height, game.canvas.width]; }")
    left, top, w, h, cw = box
    return left + x * w / cw, top + h * 0.06


def wait_for(page, cond, timeout=30.0, poll=0.03):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = page.evaluate(READ_JS)
        if st and cond(st):
            return st
        time.sleep(poll)
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--agent", default="mc", choices=["random", "typematch", "mc", "value"])
    p.add_argument("--mode", default="combined", choices=["random", "steps", "combined"])
    p.add_argument("--plies", type=int, default=1)
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--frames", type=int, default=120)
    p.add_argument("--model", default=None)
    p.add_argument("--device", default="cpu")
    p.add_argument("--hz", type=int, default=0, help="display refresh rate of the page (0 = measure)")
    p.add_argument("--no-pause", action="store_true", help="do not pause the page's physics while thinking")
    p.add_argument("--log", default=None, help="save each move (page state + chosen x) to this JSON file")
    p.add_argument("--seed", type=int, default=None,
                   help="make the page deal the same fruits as the engine with this seed")
    p.add_argument("--url", default=URL)
    args = p.parse_args()

    from playwright.sync_api import sync_playwright  # imported here so other modules don't need it

    with sync_playwright() as pw, Engine() as eng:
        browser = pw.chromium.launch(headless=False)
        page = browser.new_page(viewport={"width": 1100, "height": 900})
        if args.seed is not None:
            page.add_init_script(SEED_INIT_JS.replace("__SEED__", str(args.seed)))
        page.goto(args.url, wait_until="domcontentloaded")
        input("\n브라우저에서 팝업을 닫고 게임 화면이 보이면 Enter를 누르세요...")
        if args.seed is not None:
            draws = page.evaluate("() => window.__suphagoDraws")
            # the engine draws the first "next" fruit at reset, before any drop
            ref = eng.new_game(seed=args.seed)
            ok = bool(draws) and draws[0] == ref.state.next
            ref.free()
            print(f"시드 {args.seed} 과일 순서 적용: {'확인' if ok else '실패 (새로고침 후 다시 실행하세요)'}")
            if not ok:
                browser.close()
                return
        page.locator("canvas").first.scroll_into_view_if_needed()

        hz = args.hz
        if not hz:
            fps = page.evaluate(FPS_JS)
            hz = 120 if fps > 90 else 60
            print(f"화면 주사율 측정: {fps}fps -> {hz}Hz 기준으로 계산")

        agent = make_agent(args, eng.info["radius"], args.seed if args.seed is not None else int(time.time()))
        print(f"에이전트: {agent.name}")
        moves = []
        t_start = time.time()
        while True:
            st = wait_for(page, lambda s: s["isOver"] or (s["canDrop"] and s["next"] is not None), timeout=60)
            if st is None:
                print("페이지가 다음 수를 받을 준비가 되지 않았습니다 (60초). 종료합니다.")
                break
            if st["isOver"]:
                break
            if not args.no_pause:
                page.evaluate(PAUSE_JS)
                st = page.evaluate(READ_JS)  # exact board the agent will drop into
            t0 = time.time()
            g = eng.load_game({"score": st["score"], "current": st["current"], "next": st["next"], "fruits": st["fruits"]}, hz=hz)
            x = agent.act(g)
            g.free()
            think = time.time() - t0
            if not args.no_pause:
                page.evaluate(RESUME_JS)
            cx, cy = canvas_point(page, x)
            page.mouse.move(cx, cy)
            page.mouse.down()
            page.mouse.up()
            moves.append({"state": st, "x": x, "think": round(think, 2)})
            print(f"{len(moves):4d}수  점수 {st['score']:5d}  과일 {len(st['fruits']):2d}개  x={x:6.1f}  생각 {think:4.1f}초", flush=True)
            # wait until the page has taken the drop (preview disappears)
            wait_for(page, lambda s: s["isOver"] or not s["canDrop"], timeout=5)

        final = page.evaluate(READ_JS) or {"score": None}
        print(f"\n게임 종료: {final['score']}점, {len(moves)}수, {time.time() - t_start:.0f}초")
        if args.log:
            Path(args.log).write_text(json.dumps({"agent": agent.name, "hz": hz, "pause": not args.no_pause,
                                                  "finalScore": final["score"], "moves": moves}))
            print(f"기록 저장: {args.log}")
        input("Enter를 누르면 브라우저를 닫습니다...")
        browser.close()


if __name__ == "__main__":
    main()
