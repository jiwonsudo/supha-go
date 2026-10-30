'use strict';
// Long look-ahead for search: from a game, drop at x and then keep playing with a fast
// built-in policy for up to `length` more moves, on fruits drawn from a fresh seed (the
// real future fruits are unknown to a player, so the copy's fruit RNG is replaced).
const { RADIUS } = require('./suika');

const WALL_L = 55, WALL_R = 599, HEIGHT = 724;

function mulberry(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Top of the pile among fruits at rest (same rule as server.js).
const topY = (g) => g.fruits.reduce((m, f) => (f.body.speed < 1 ? Math.min(m, f.body.position.y - RADIUS[f.type]) : m), HEIGHT);

// x positions of same-type fruits a straight drop would hit first (agents.py reachable_matches).
function reachableMatches(g) {
  const t = g.current, rc = RADIUS[t];
  const lo = WALL_L + rc, hi = WALL_R - rc;
  const xs = [];
  for (const f of g.fruits) {
    if (f.type !== t) continue;
    const x = Math.min(Math.max(f.body.position.x, lo), hi);
    let best = null, bestY = Infinity;
    for (const o of g.fruits) {
      const reach = rc + RADIUS[o.type];
      const dx = Math.abs(o.body.position.x - x);
      if (dx >= reach) continue;
      const y = o.body.position.y - Math.sqrt(reach * reach - dx * dx);
      if (y < bestY) { best = o; bestY = y; }
    }
    if (best === f) xs.push(x);
  }
  return xs;
}

// Fast policy for the rest of a rollout.
//   k = 0: typematch (same-type fruit if one can be hit, else random), no simulation.
//   k > 0: k candidates (same-type first, rest random), each simulated for `frames`
//          frames and scored +3 per removed fruit, +1 if the pile did not grow.
function policyMove(g, rng, k, frames) {
  const t = g.current, lo = WALL_L + RADIUS[t], hi = WALL_R - RADIUS[t];
  const xs = reachableMatches(g);
  if (k === 0) return xs.length ? xs[Math.floor(rng() * xs.length)] : lo + rng() * (hi - lo);
  xs.length = Math.min(xs.length, k);
  while (xs.length < k) xs.push(lo + rng() * (hi - lo));
  const n0 = g.fruits.length, top0 = topY(g);
  let best = -Infinity, pick = [];
  for (const x of xs) {
    const c = g.clone();
    c.drop(x);
    for (let i = 0; i < frames && !c.isOver; i++) c.stepFrame();
    const v = c.isOver ? -1000 : 3 * (n0 + 1 - c.fruits.length) + (topY(c) >= top0 ? 1 : 0);
    if (v > best) { best = v; pick = [x]; } else if (v === best) pick.push(x);
  }
  return pick[Math.floor(rng() * pick.length)];
}

// For each x: `count` rollouts of drop-at-x then up to `length` policy moves.
// Each result: mean points gained, share of rollouts that ended the game, mean moves
// survived (the first drop included), and the share that cleared two watermelons.
function rollout(g, xs, { count = 8, length = 50, k = 0, frames = 36, seed = 1 } = {}) {
  return xs.map((x, i) => {
    let gain = 0, over = 0, moves = 0, cleared = 0;
    for (let r = 0; r < count; r++) {
      const c = g.clone();
      // Same seeds for every candidate (common random numbers), so candidates are
      // compared on the same future fruits and the comparison is less noisy.
      c._rngState = (seed * 1000003 + r * 7919) >>> 0;
      const rng = mulberry(seed * 31 + r * 104729 + 17);
      const s0 = c.score;
      c.merged = new Array(11).fill(0); // merge counts by type (suika.js fills it in)
      c.turn(x);
      let m = 1;
      while (!c.isOver && m <= length) {
        c.turn(policyMove(c, rng, k, frames));
        m++;
      }
      gain += c.score - s0;
      if (c.isOver) over++;
      moves += m;
      if (c.merged[10] > 0) cleared++;
    }
    return { x, gain: gain / count, over: over / count, moves: moves / count, cleared: cleared / count };
  });
}

module.exports = { rollout, policyMove, reachableMatches };
