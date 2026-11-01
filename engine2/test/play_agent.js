// Play full engine2 games with the JS agent: node test/play_agent.js seed0 games
const { SuikaGame2 } = require('../src/suika2');
const { chooseMove } = require('../src/agent');
const s0 = +(process.argv[2] || 0), n = +(process.argv[3] || 1);
for (let seed = s0; seed < s0 + n; seed++) {
  const g = new SuikaGame2({ seed });
  let r = seed * 7919 + 1;
  const rng = () => ((r = (Math.imul(r, 1103515245) + 12345) >>> 0) / 4294967296);
  const t0 = Date.now(); let turns = 0;
  while (!g.isOver) { g.turn(chooseMove(g, rng).x); turns++; }
  console.log(JSON.stringify({ seed, score: g.score, turns, sec: Math.round((Date.now() - t0) / 1000), msPerMove: Math.round((Date.now() - t0) / turns) }));
}
