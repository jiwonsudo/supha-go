'use strict';
// Prints a hash of full game states over several seeded games.
// Optimizations must keep this hash unchanged.
const crypto = require('crypto');
const { SuikaGame, RADIUS, MARGIN_X, WIDTH } = require('../src/suika');

const h = crypto.createHash('sha256');
let s = 12345;
const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
let turns = 0;
const t0 = Date.now();
for (let seed = 0; seed < 4; seed++) {
  const g = new SuikaGame({ seed, displayHz: 60 });
  while (!g.isOver) {
    const r = RADIUS[g.current];
    g.turn(MARGIN_X + r + rnd() * (WIDTH - 2 * MARGIN_X - 2 * r));
    turns++;
    h.update(JSON.stringify(g.state()));
  }
}
console.log(h.digest('hex').slice(0, 16), `${turns} turns, ${((Date.now() - t0) / turns).toFixed(2)} ms/turn`);
