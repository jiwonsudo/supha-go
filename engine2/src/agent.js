'use strict';
// Monte Carlo agent for engine2, the same as python/suphago/agents.py MonteCarloAgent with
// plies=2, mode="combined" and the board-shape terms (chain, inv), so it can run inside the
// contest page without Python. Works in world coordinates (x centred, y up).
const { RADIUS, WIDTH, PTM } = require('./suika2');

const GAME_OVER = -1000;
const xRange = (t) => [-360 + RADIUS[t], 360 - RADIUS[t]];
const pos = (f) => f.body.GetPosition();
const X = (f) => pos(f).x * PTM;
const Y = (f) => pos(f).y * PTM;
// highest point among fruits at rest (y up, bigger = higher); speed < 1 px per frame
const top = (g) => g.fruits.reduce((m, f) => (f.body.GetLinearVelocity().Length() * PTM / 60 < 1 ? Math.max(m, Y(f) + RADIUS[f.type]) : m), -1360);

// same-type fruits a straight drop of the current fruit would hit first
function reachableMatches(g) {
  const t = g.current, rc = RADIUS[t];
  const [lo, hi] = xRange(t);
  const xs = [];
  for (const f of g.fruits) {
    if (f.type !== t) continue;
    const x = Math.min(Math.max(X(f), lo), hi);
    let best = null, bestY = -Infinity;
    for (const o of g.fruits) {
      const reach = rc + RADIUS[o.type];
      const dx = Math.abs(X(o) - x);
      if (dx >= reach) continue;
      const y = Y(o) + Math.sqrt(reach * reach - dx * dx);
      if (y > bestY) { best = o; bestY = y; }
    }
    if (best === f) xs.push(x);
  }
  return xs;
}

// Board-shape terms on the end board (agents.py shape_bonus with small = long = 0).
function shape(g, chain, inv) {
  const fs = g.fruits;
  let links = 0, flips = 0;
  for (const a of fs) {
    for (const b of fs) {
      if (a === b) continue;
      if (chain && b.type === a.type + 1 && a.type >= 4 && Math.hypot(X(a) - X(b), Y(a) - Y(b)) - RADIUS[a.type] - RADIUS[b.type] < 15) links++;
      // b above a (y up), b at least two sizes bigger, overlapping in x
      if (inv && Y(b) > Y(a) && b.type > a.type + 1 && Math.abs(X(b) - X(a)) < RADIUS[a.type] + RADIUS[b.type] * 0.5) flips++;
    }
  }
  return chain * links - inv * flips;
}

// One candidate: drop at x, 120 frames, then the known next fruit at x2, 120 frames.
function score(g0, x, x2, { frames = 120, chain = 1, inv = 0.3 } = {}) {
  const c = g0.clone();
  const n0 = c.fruits.length, top0 = top(c), type = c.current;
  c.drop(x);
  const dropped = c.fruits[c.fruits.length - 1];
  for (let k = 0; k < frames && !c.isOver; k++) c.stepFrame();
  if (c.isOver) return GAME_OVER;
  let touchNext = 0;
  if (dropped.alive && type < 10) {
    for (const f of c.fruits) {
      if (f.type === type + 1 && Math.hypot(X(f) - X(dropped), Y(f) - Y(dropped)) < RADIUS[f.type] + RADIUS[type] + 1) touchNext++;
    }
  }
  const top1 = top(c);
  let v = 3 * (n0 + 1 - c.fruits.length) + (top1 <= top0 ? 1 : 0) + touchNext;
  while (!c.canDrop && !c.isOver) c.stepFrame();
  if (c.isOver) return GAME_OVER;
  const n1 = c.fruits.length;
  c.drop(x2);
  for (let k = 0; k < frames && !c.isOver; k++) c.stepFrame();
  if (c.isOver) return GAME_OVER;
  v += 3 * (n1 + 1 - c.fruits.length) + (top(c) <= top1 ? 1 : 0);
  return v + shape(c, chain, inv);
}

// Pick a drop x (world px) for game g. rng: () => [0, 1).
function chooseMove(g, rng, { n = 50, frames = 120, chain = 1, inv = 0.3 } = {}) {
  const [lo, hi] = xRange(g.current);
  const xs = reachableMatches(g).slice(0, n);
  while (xs.length < n) xs.push(lo + rng() * (hi - lo));
  const [lo2, hi2] = xRange(g.next);
  const scores = xs.map((x) => score(g, x, lo2 + rng() * (hi2 - lo2), { frames, chain, inv }));
  const best = Math.max(...scores);
  const ties = xs.filter((x, i) => scores[i] === best);
  return { x: ties[Math.floor(rng() * ties.length)], best, scores, xs };
}

module.exports = { chooseMove, reachableMatches, shape, score };
