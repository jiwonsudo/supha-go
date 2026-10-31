// Runs inside the contest page (paste after __SUIKA2_SRC__ is replaced by engine2/src/suika2.js).
// Pauses the page's game loop and steps it one 1/60 s frame at a time. For each move: reads the
// page's board, builds engine2 from it, drops at the same x in both, runs both until the next
// fruit can be dropped, and compares. Returns a summary; details stay in window.PC.
(() => {
  const PTM = 32;
  // engine2 on the page's own Box2D (window.b2 holds box2d with the "b2" prefix removed)
  const shim = {};
  for (const k in b2) shim['b2' + k] = b2[k];
  const mod = { exports: {} };
  new Function('require', 'module', 'exports', __SUIKA2_SRC__)(() => shim, mod, mod.exports);
  const { SuikaGame2 } = mod.exports;

  const gf = cc.find('Canvas/gameManager').getComponent('GameFunction');
  const ic = cc.find('Canvas/inputNode').getComponent('InputController');
  const canvas = cc.find('Canvas');
  cc.game.pause();
  cc.director.calculateDeltaTime = function () { this._deltaTime = 1 / 60; };
  const step = () => cc.director.mainLoop(performance.now());

  const nodes = () => {
    const out = [];
    for (const parent of [cc.find('Canvas/fruitNode'), cc.find('Canvas/lineNode')]) {
      for (const n of parent.children) {
        const fd = n.getComponent('fruitData');
        if (!fd || n === gf.targetFruit || !n.active) continue;
        const rb = n.getComponent(cc.RigidBody);
        if (!rb || !rb._b2Body) continue;
        out.push({ n, fd, b: rb._b2Body, col: n.getComponent(cc.PhysicsCircleCollider), inBox: parent.name === 'fruitNode' });
      }
    }
    return out;
  };
  const read = () => {
    const cw = canvas.convertToWorldSpaceAR(cc.v2(0, 0));
    return nodes().map(({ n, fd, b, col, inBox }) => {
      const p = b.GetPosition(), v = b.GetLinearVelocity();
      return { type: fd.fruitNumber, x: p.x - cw.x / PTM, y: p.y - cw.y / PTM, vx: v.x, vy: v.y, a: b.GetAngle(), av: b.GetAngularVelocity(),
        scale: n.scale, rad: col ? col.radius : 0, inBox, touched: !!fd.endCtrl, merged: fd.pengzhuangCount, boxTime: fd.testEndDJS,
        numberUsed: fd.getNumberTime, numberReset: -1, busy: false, awake: b.IsAwake() };
    });
  };
  const settled = (fs) => fs.every((f) => f.scale === 1 && f.rad > 1);

  // greedy match by type, nearest first; returns position errors (px) and unmatched counts
  const match = (A, B) => {
    const errs = []; let miss = 0;
    const used = new Set();
    for (const a of A) {
      let best = -1, bd = Infinity;
      B.forEach((b, j) => { if (used.has(j) || b.type !== a.type) return; const d = Math.hypot(a.x - b.x, a.y - b.y) * PTM; if (d < bd) { bd = d; best = j; } });
      if (best < 0) miss++; else { used.add(best); errs.push(bd); }
    }
    return { errs, miss: miss + (B.length - used.size) };
  };

  const PC = window.PC = { moves: [] };
  PC.run = (count, seed = 1) => {
    let r = seed;
    const rand = () => ((r = (r * 1103515245 + 12345) >>> 0) / 4294967296);
    for (let m = 0; m < count; m++) {
      let guard = 0;
      while ((!gf.targetFruit) && guard++ < 600) step();
      if (!gf.targetFruit) { PC.moves.push({ end: true }); break; }
      const before = read();
      const cur = gf.targetFruit.getComponent('fruitData').fruitNumber;
      const xBox = 30 + rand() * 660;
      const winH = cc.winSize.height;
      // engine2 from the page's board
      const g = SuikaGame2.restore({
        g: { hz: 60, winH, score: 0, isOver: false, frame: 0, drops: 10, current: cur, next: 0, canDrop: true, waitFrames: 0, blockFrames: 0, _rngState: 1 },
        fruits: before, timers: [],
      });
      // page: same drop as InputController.onTouchEnd after a drag to x
      gf.targetFruit.x = xBox - 360;
      ic.touchNum = 1;
      ic.onTouchEnd({});
      let frames = 0;
      do { step(); frames++; } while (!gf.targetFruit && frames < 600);
      g.drop(xBox - 360);
      for (let k = 0; k < frames; k++) g.stepFrame();
      const after = read();
      const pred = g.snapshot().fruits;
      const mm = match(after, pred);
      PC.moves.push({ m, xBox, cur, frames, wasSettled: settled(before), nBefore: before.length, nAfter: after.length, nPred: pred.length,
        maxErr: Math.max(0, ...mm.errs), medErr: mm.errs.sort((a, b) => a - b)[mm.errs.length >> 1] || 0, miss: mm.miss, winH });
    }
    const ok = PC.moves.filter((x) => !x.end);
    const q = (arr, p) => { const s = arr.slice().sort((a, b) => a - b); return s.length ? +s[Math.floor(p * (s.length - 1))].toFixed(2) : null; };
    return {
      moves: ok.length, winH: ok[0] && ok[0].winH,
      sameCount: ok.filter((x) => x.nAfter === x.nPred).length,
      noMiss: ok.filter((x) => x.miss === 0).length,
      medErr: { p50: q(ok.map((x) => x.medErr), 0.5), p90: q(ok.map((x) => x.medErr), 0.9) },
      maxErr: { p50: q(ok.map((x) => x.maxErr), 0.5), p90: q(ok.map((x) => x.maxErr), 0.9) },
      frames: [...new Set(ok.map((x) => x.frames))],
      last: ok.slice(-3),
    };
  };
  return 'ready';
})();
