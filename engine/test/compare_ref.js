'use strict';
// Replays the scripted scenario recorded on playsuikagame.com and compares positions.
const path = require('path');
const ref = require(path.join(__dirname, 'ref_original_120hz.json'));
const { SuikaGame } = require('../src/suika');

const g = new SuikaGame({ seed: 0, displayHz: 120 });
console.log('wall ids', g.world.bodies.map((b) => b.id).join(','));

const snaps = [];
let di = 0;
for (let frame = 0; ; frame++) {
  g.stepFrame();
  if (frame % ref.GAP === 0) {
    if (di > 0) snaps.push({ frame, score: g.score, f: g.fruits.map((f) => ['fruit' + f.type, f.body.position.x, f.body.position.y]) });
    if (di < ref.drops.length) {
      g._addFruit(parseInt(ref.drops[di].t.replace('fruit', ''), 10), ref.drops[di].x, 80);
      di++;
    } else break;
  }
}

let worst = 0;
let firstDiverge = null;
ref.rec.forEach((r, i) => {
  const s = snaps[i];
  const sameSet = s.score === r.score && s.f.length === r.f.length && s.f.every((f, j) => f[0] === r.f[j][0]);
  let maxErr = 0;
  if (sameSet) s.f.forEach((f, j) => { maxErr = Math.max(maxErr, Math.hypot(f[1] - r.f[j][1], f[2] - r.f[j][2])); });
  else maxErr = Infinity;
  worst = Math.max(worst, maxErr);
  if (firstDiverge === null && maxErr > 0.01) firstDiverge = r.frame;
  console.log(`frame ${r.frame}: score ref ${r.score} / clone ${s.score}, fruits ${r.f.length}/${s.f.length}, max pos err ${maxErr === Infinity ? 'MISMATCH' : maxErr.toFixed(4)}`);
});
console.log('worst', worst, 'first divergence frame', firstDiverge);
