'use strict';
// JSON-lines worker for the contest-site engine (suika2.js), same protocol as engine/src/server.js
// for the commands the Monte Carlo agents use. x values from Python are box coordinates
// (0 = left wall, 720 = right wall); state() reports y-down box coordinates (see suika2.js).
const readline = require('readline');
const { SuikaGame2, RADIUS } = require('./suika2');

const games = new Map();
let nextHandle = 1;
const get = (h) => { const g = games.get(h); if (!g) throw new Error(`unknown game ${h}`); return g; };
const X0 = 360;
const boxY = (f) => 640 - f.body.GetPosition().y * 32;
const boxX = (f) => f.body.GetPosition().x * 32 + X0;

// Highest point of the pile among fruits at rest (y-down, smaller = higher).
const topY = (g) => g.fruits.reduce((m, f) => (f.body.GetLinearVelocity().Length() * 32 / 60 < 1 ? Math.min(m, boxY(f) - RADIUS[f.type]) : m), 2000);

function evaluate(g, xs, frames, secondXs, withState) {
  const base = { score: g.score, n: g.fruits.length, top: topY(g) };
  return xs.map((x, i) => {
    const c = g.clone();
    c.merged = new Array(11).fill(0);
    const type = c.current;
    c.drop(x - X0);
    const dropped = c.fruits[c.fruits.length - 1];
    for (let k = 0; k < frames && !c.isOver; k++) c.stepFrame();
    let touchNext = 0;
    if (dropped.alive && type < 10) {
      for (const f of c.fruits) {
        if (f.type !== type + 1) continue;
        const d = Math.hypot(boxX(f) - boxX(dropped), boxY(f) - boxY(dropped));
        if (d < RADIUS[f.type] + RADIUS[type] + 1) touchNext++;
      }
    }
    const first = {
      gain: c.score - base.score,
      removed: base.n + 1 - c.fruits.length,
      topBefore: base.top,
      topAfter: topY(c),
      droppedAlive: dropped.alive,
      touchNext,
      isOver: c.isOver,
      merged: c.merged.slice(),
    };
    if (withState && !c.isOver) first.state = c.state();
    if (!secondXs || c.isOver) return first;
    while (!c.canDrop && !c.isOver) c.stepFrame();
    const s2 = c.score, n2 = c.fruits.length;
    if (!c.isOver) {
      c.drop(secondXs[i] - X0);
      for (let k = 0; k < frames && !c.isOver; k++) c.stepFrame();
    }
    first.second = { gain: c.score - s2, removed: n2 + 1 - c.fruits.length, topAfter: topY(c), isOver: c.isOver,
      merged: c.merged.map((v, t) => v - first.merged[t]) };
    if (withState && !c.isOver) first.second.state = c.state();
    return first;
  });
}

const handlers = {
  info: () => ({ engine: 'suika2', radius: RADIUS, walls: [0, 720] }),
  new: ({ seed = 0, hz = 60, winH = 1262.5 }) => {
    const h = nextHandle++;
    games.set(h, new SuikaGame2({ seed, hz, winH }));
    return { id: h, state: games.get(h).state() };
  },
  state: ({ id }) => get(id).state(),
  turn: ({ id, x, extra = 0 }) => {
    const g = get(id);
    const gain = g.turn(x - X0, extra);
    return { gain, state: g.state() };
  },
  clone: ({ id }) => { const h = nextHandle++; games.set(h, get(id).clone()); return { id: h }; },
  free: ({ id }) => ({ ok: games.delete(id) }),
  freeMany: ({ ids }) => ({ freed: ids.filter((i) => games.delete(i)).length }),
  evaluate: ({ id, xs, frames = 120, secondXs = null, withState = false }) => evaluate(get(id), xs, frames, secondXs, withState),
};

const rl = readline.createInterface({ input: process.stdin });
rl.on('line', (line) => {
  let req;
  try {
    req = JSON.parse(line);
    const fn = handlers[req.cmd];
    if (!fn) throw new Error(`unknown cmd ${req.cmd}`);
    process.stdout.write(JSON.stringify({ ok: true, result: fn(req) }) + '\n');
  } catch (e) {
    process.stdout.write(JSON.stringify({ ok: false, error: String(e && e.message) }) + '\n');
  }
});
