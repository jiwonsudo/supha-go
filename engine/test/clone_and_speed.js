'use strict';
// 1) clone() must branch with identical results. 2) Measure random-play speed.
const { SuikaGame, RADIUS, MARGIN_X, WIDTH } = require('../src/suika');

function randomX(g, rnd) {
  const r = RADIUS[g.current];
  return MARGIN_X + r + rnd() * (WIDTH - 2 * MARGIN_X - 2 * r);
}

let s = 99;
const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);

// clone determinism
const g = new SuikaGame({ seed: 42 });
for (let i = 0; i < 60 && !g.isOver; i++) g.turn(randomX(g, rnd));
const c = g.clone();
const xs = [];
for (let i = 0; i < 80; i++) xs.push(rnd());
const play = (game) => {
  for (const u of xs) {
    if (game.isOver) break;
    const r = RADIUS[game.current];
    game.turn(MARGIN_X + r + u * (WIDTH - 2 * MARGIN_X - 2 * r));
  }
  return JSON.stringify(game.state());
};
const a = play(g), b = play(c);
console.log('clone identical:', a === b, 'score', JSON.parse(a).score);

// speed
const t0 = Date.now();
let turns = 0, games = 0, totalScore = 0;
while (Date.now() - t0 < 20000) {
  const h = new SuikaGame({ seed: games, displayHz: 60 });
  while (!h.isOver && turns < 1e9) { h.turn(randomX(h, rnd)); turns++; }
  games++;
  totalScore += h.score;
}
const sec = (Date.now() - t0) / 1000;
console.log(`random play: ${games} games, ${turns} turns in ${sec.toFixed(1)}s -> ${(turns / sec).toFixed(0)} turns/s/core, avg score ${(totalScore / games).toFixed(0)}`);

const h = new SuikaGame({ seed: 1 });
for (let i = 0; i < 150 && !h.isOver; i++) h.turn(randomX(h, rnd));
const t1 = Date.now();
for (let i = 0; i < 300; i++) h.clone();
console.log(`clone with ${h.fruits.length} fruits: ${((Date.now() - t1) / 300).toFixed(2)} ms`);
