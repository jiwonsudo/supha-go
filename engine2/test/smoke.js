const { SuikaGame2, RADIUS } = require('../src/suika2');
for (const seed of [0, 1, 2]) {
  const g = new SuikaGame2({ seed });
  const t0 = Date.now(); let turns = 0, maxT = 0, maxN = 0;
  while (!g.isOver && turns < 3000) {
    // typematch-ish: drop on a same-type fruit if any, else random
    const same = g.fruits.filter(f => f.type === g.current);
    const x = same.length ? same[0].body.GetPosition().x * 32 : (g.rng() * 2 - 1) * 330;
    g.turn(x); turns++;
    maxN = Math.max(maxN, g.fruits.length);
    for (const f of g.fruits) maxT = Math.max(maxT, f.type);
  }
  const t1 = Date.now();
  const c = g.clone(); const t2 = Date.now();
  console.log(JSON.stringify({ seed, score: g.score, turns, frames: g.frame, maxType: maxT, maxFruits: maxN, ms: t1 - t0, msPerFrame: +((t1 - t0) / g.frame).toFixed(3), cloneMs: t2 - t1 }));
}
// clone determinism: play a mid game, clone, continue both identically
const g = new SuikaGame2({ seed: 7 });
for (let i = 0; i < 60; i++) g.turn(((i * 97) % 600) - 300);
const c = g.clone();
for (let i = 0; i < 40; i++) { const x = ((i * 53) % 600) - 300; g.turn(x); c.turn(x); }
const a = JSON.stringify(g.state()), b = JSON.stringify(c.state());
console.log('clone same after 40 turns:', a === b, g.score, c.score, g.fruits.length, c.fruits.length);
