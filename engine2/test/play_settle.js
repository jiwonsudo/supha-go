// Like play_agent.js, with a choice of how long to wait before each move:
//   node test/play_settle.js seed0 games mode    mode: none | timers | calm
// none: as soon as the next fruit can be dropped (64 frames); timers: until no merge pull or
// scale-in is running; calm: also until nothing moves faster than 0.5 px/frame (the first live runs).
const { SuikaGame2 } = require('../src/suika2');
const { chooseMove } = require('../src/agent');
const s0 = +(process.argv[2] || 0), n = +(process.argv[3] || 1);
for (let seed = s0; seed < s0 + n; seed++) {
  const g = new SuikaGame2({ seed });
  let r = seed * 7919 + 1;
  const rng = () => ((r = (Math.imul(r, 1103515245) + 12345) >>> 0) / 4294967296);
  const mode = process.argv[4] || 'calm';
  const calm = () => mode === 'none' || g.timers.length === 0 && g.fruits.every((f) => f.scale === 1 && (mode === 'timers' || f.body.GetLinearVelocity().Length() * 32 / 60 < 0.5));
  let turns = 0, waited = 0;
  while (!g.isOver) {
    let w = 0; while (!calm() && !g.isOver && w++ < 900) { g.stepFrame(); waited++; }
    if (g.isOver) break;
    g.turn(chooseMove(g, rng).x); turns++;
  }
  console.log(JSON.stringify({ seed, settle: mode, score: g.score, turns, avgWait: Math.round(waited / turns) }));
}
