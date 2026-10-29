'use strict';
// JSON-lines worker: one request per line on stdin, one response per line on stdout.
// Python drives several of these processes in parallel (see python/suphago/bridge.py).
const readline = require('readline');
const { SuikaGame, RADIUS, MERGE_SCORE, WIDTH, HEIGHT, MARGIN_X, DROP_Y } = require('./suika');

const games = new Map();
let nextHandle = 1;

// Top of the pile, counting only fruits that have come to rest (a fruit still falling
// from the previous drop would otherwise look like the highest point).
const topY = (g) => g.fruits.reduce((m, f) => (f.body.speed < 1 ? Math.min(m, f.body.position.y - RADIUS[f.type]) : m), HEIGHT);

function get(h) {
  const g = games.get(h);
  if (!g) throw new Error(`unknown game ${h}`);
  return g;
}

// Branch from game g, drop at each x, run `frames` frames after the drop, and report
// what happened. Used by search agents; g itself is not changed.
function evaluate(g, xs, frames, secondXs, withState) {
  const base = { score: g.score, n: g.fruits.length, top: topY(g) };
  return xs.map((x, i) => {
    const c = g.clone();
    c.merged = new Array(11).fill(0);
    const type = c.current;
    c.drop(x);
    const dropped = c.fruits[c.fruits.length - 1];
    for (let k = 0; k < frames && !c.isOver; k++) c.stepFrame();
    let touchNext = 0;
    if (dropped.alive && type < 10) {
      for (const f of c.fruits) {
        if (f.type !== type + 1) continue;
        const d = Math.hypot(f.body.position.x - dropped.body.position.x, f.body.position.y - dropped.body.position.y);
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
    // second ply with the known next fruit
    while (!c.canDrop && !c.isOver) c.stepFrame();
    const s2 = c.score, n2 = c.fruits.length;
    if (!c.isOver) {
      c.drop(secondXs[i]);
      for (let k = 0; k < frames && !c.isOver; k++) c.stepFrame();
    }
    first.second = { gain: c.score - s2, removed: n2 + 1 - c.fruits.length, topAfter: topY(c), isOver: c.isOver,
      merged: c.merged.map((v, t) => v - first.merged[t]) };
    if (withState && !c.isOver) first.second.state = c.state();
    return first;
  });
}

// Branch from game g, drop at each x and run until the next drop is allowed (the
// point where the agent decides again). Returns the score gained and that state.
// Also returns the same counts the Monte Carlo heuristic uses, so an agent can mix the two.
function expand(g, xs) {
  const n0 = g.fruits.length, top0 = topY(g);
  return xs.map((x) => {
    const c = g.clone();
    const before = c.score;
    const type = c.current;
    c.drop(x);
    const dropped = c.fruits[c.fruits.length - 1];
    while (!c.canDrop && !c.isOver) c.stepFrame();
    let touchNext = 0;
    if (dropped.alive && type < 10) {
      for (const f of c.fruits) {
        if (f.type !== type + 1) continue;
        const d = Math.hypot(f.body.position.x - dropped.body.position.x, f.body.position.y - dropped.body.position.y);
        if (d < RADIUS[f.type] + RADIUS[type] + 1) touchNext++;
      }
    }
    return {
      gain: c.score - before, isOver: c.isOver, state: c.state(),
      removed: n0 + 1 - c.fruits.length, topBefore: top0, topAfter: topY(c), touchNext,
    };
  });
}

// Same as turn, but also returns body positions every `every` frames for the replay
// viewer. Each snapshot is a flat int array: id, type, x*10, y*10, angle*100, ...
// The dropped fruit is captured from its first frame.
function turnRecorded(g, x, every) {
  const before = g.score;
  const snap = () => {
    const a = [];
    for (const f of g.fruits) {
      const b = f.body;
      a.push(b.id, f.type, Math.round(b.position.x * 10), Math.round(b.position.y * 10), Math.round(b.angle * 100));
    }
    return a;
  };
  if (!g.drop(x)) return { gain: 0, frames: [], state: g.state() };
  const frames = [snap()];
  let k = 0;
  while (!g.canDrop && !g.isOver) {
    g.stepFrame();
    if (++k % every === 0) frames.push(snap());
  }
  if (k % every !== 0) frames.push(snap());
  return { gain: g.score - before, frames, state: g.state() };
}

const handlers = {
  load: ({ state, seed = 0, hz = 60 }) => {
    const h = nextHandle++;
    games.set(h, SuikaGame.fromState(state, { seed, displayHz: hz }));
    return { id: h, state: games.get(h).state() };
  },
  // advance a game by n frames without dropping (used to compare against a real page)
  run: ({ id, frames }) => {
    const g = get(id);
    for (let i = 0; i < frames && !g.isOver; i++) g.stepFrame();
    return g.state();
  },
  expand: ({ id, xs }) => expand(get(id), xs),
  turnRecorded: ({ id, x, every = 2 }) => turnRecorded(get(id), x, every),
  info: () => ({ radius: RADIUS, mergeScore: MERGE_SCORE, width: WIDTH, height: HEIGHT, marginX: MARGIN_X, dropY: DROP_Y }),
  new: ({ seed = 0, hz = 60 }) => {
    const h = nextHandle++;
    games.set(h, new SuikaGame({ seed, displayHz: hz }));
    return { id: h, state: games.get(h).state() };
  },
  state: ({ id }) => get(id).state(),
  turn: ({ id, x, extra = 0 }) => {
    const g = get(id);
    const gain = g.turn(x, extra);
    return { gain, state: g.state() };
  },
  clone: ({ id }) => {
    const h = nextHandle++;
    games.set(h, get(id).clone());
    return { id: h };
  },
  free: ({ id }) => ({ ok: games.delete(id) }),
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
