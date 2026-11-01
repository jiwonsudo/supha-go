// Plays the contest page with the JS agent (engine2/src/agent.js), inside the page.
// Load: replace __SUIKA2_SRC__ / __AGENT_SRC__ with the sources, eval, then AP.start().
// The page's game loop is paused; the script steps it 1/60 s per frame (as a 60 Hz display
// would), waits for a settled board before each move, drops with InputController.onTouchEnd
// after placing the waiting fruit at x, and after game over resumes the normal loop so the
// end bonus and the result screen play out. Progress: AP.status(). Results: AP.games.
(() => {
  const PTM = 32;
  const shim = {};
  for (const k in b2) shim['b2' + k] = b2[k];
  const mods = {};
  const load = (name, src) => {
    const mod = { exports: {} };
    new Function('require', 'module', 'exports', src)((p) => (p.includes('box2d') ? shim : mods[p.replace(/^.*\//, './')]), mod, mod.exports);
    mods[name] = mod.exports;
  };
  load('./suika2', __SUIKA2_SRC__);
  load('./agent', __AGENT_SRC__);
  const { SuikaGame2 } = mods['./suika2'];
  const { chooseMove } = mods['./agent'];

  const PI = window.__require('PlayerInfo').default;
  const gf = () => cc.find('Canvas/gameManager').getComponent('GameFunction');
  const ic = () => cc.find('Canvas/inputNode').getComponent('InputController');
  const canvas = () => cc.find('Canvas');
  const step = () => cc.director.mainLoop(performance.now());
  const fixedDt = function () { this._deltaTime = 1 / 60; };
  const origDt = cc.director.calculateDeltaTime;

  const read = () => {
    const cw = canvas().convertToWorldSpaceAR(cc.v2(0, 0));
    const out = [];
    for (const parent of [cc.find('Canvas/fruitNode'), cc.find('Canvas/lineNode')]) {
      for (const n of parent.children) {
        const fd = n.getComponent('fruitData');
        if (!fd || n === gf().targetFruit || !n.active) continue;
        const rb = n.getComponent(cc.RigidBody);
        if (!rb || !rb._b2Body) continue;
        const b = rb._b2Body, p = b.GetPosition(), v = b.GetLinearVelocity(), col = n.getComponent(cc.PhysicsCircleCollider);
        out.push({ type: fd.fruitNumber, x: p.x - cw.x / PTM, y: p.y - cw.y / PTM, vx: v.x, vy: v.y, a: b.GetAngle(), av: b.GetAngularVelocity(),
          scale: n.scale, rad: col ? col.radius : 0, inBox: parent.name === 'fruitNode', touched: !!fd.endCtrl, merged: fd.pengzhuangCount,
          boxTime: fd.testEndDJS, numberUsed: fd.getNumberTime, numberReset: -1, busy: false, awake: b.IsAwake() });
      }
    }
    return out;
  };
  const calm = (fs) => fs.every((f) => f.scale === 1 && f.rad > 1 && Math.hypot(f.vx, f.vy) * PTM / 60 < 0.5);
  const over = () => !PI.GameUpdateCtrl;

  let r = (Date.now() >>> 0) || 1;
  const rng = () => ((r = (Math.imul(r, 1103515245) + 12345) >>> 0) / 4294967296);

  const AP = window.AP = { games: [], moves: 0, running: false, opts: { n: 50, chain: 2, inv: 0.6 }, log: [], record: [] };
  AP.status = () => ({ running: AP.running, moves: AP.moves, score: PI.score, over: over(), games: AP.games });

  function move() {
    const g0 = gf();
    let guard = 0;
    while ((!g0.targetFruit || !PI.playerTouch) && !over() && guard++ < 1200) step();
    if (over()) return false;
    let w = 0, fs = read();
    while (!calm(fs) && !over() && w++ < 900) { step(); fs = read(); }
    if (over() || !g0.targetFruit) return !over();
    const cur = g0.targetFruit.getComponent('fruitData').fruitNumber;
    const g = SuikaGame2.restore({
      g: { hz: 60, winH: cc.winSize.height, score: 0, isOver: false, frame: 0, drops: 10, current: cur, next: (0, eval)('next'), canDrop: true,
        waitFrames: 0, blockFrames: 0, _rngState: (rng() * 4294967296) >>> 0 },
      fruits: fs, timers: [],
    });
    const t0 = performance.now();
    const c = chooseMove(g, rng, AP.opts);
    g0.targetFruit.x = Math.max(-360 + 1, Math.min(360 - 1, c.x));
    ic().touchNum = 1;
    ic().onTouchEnd({});
    AP.moves++;
    AP.log.push({ m: AP.moves, cur, x: +c.x.toFixed(1), best: c.best, ms: Math.round(performance.now() - t0), score: PI.score });
    // whole-game record (evidence): move, current, next, drop x (canvas px), score before, fruits on the board
    AP.record.push([AP.moves, cur, g.next, +c.x.toFixed(1), PI.score, fs.length]);
    if (AP.log.length > 50) AP.log.shift();
    return true;
  }

  function finish() {
    // let the page run normally: end() adds the end bonus with real-time timeouts, then shows the result
    cc.director.calculateDeltaTime = origDt;
    cc.game.resume();
    const startScore = PI.score;
    setTimeout(() => {
      const shown = document.getElementById('ThisGameScoreResult');
      AP.games.push({ end: new Date().toISOString(), moves: AP.moves, scoreAtOver: startScore, final: PI.score,
        display: shown ? +(shown.textContent || '').trim() || null : null, winH: cc.winSize.height, opts: AP.opts });
      try { localStorage.setItem('AP.games', JSON.stringify(AP.games)); } catch (e) { /* storage may be blocked */ }
      AP.running = false;
    }, 15000);
  }

  AP.start = () => {
    if (AP.running) return 'already running';
    AP.running = true;
    AP.moves = 0;
    AP.record = [];
    AP.started = new Date().toISOString();
    cc.game.pause();
    cc.director.calculateDeltaTime = fixedDt;
    const loop = () => {
      if (!AP.running) return;
      let ok = true;
      try { ok = move(); } catch (e) { AP.error = String(e && e.stack); ok = false; }
      if (ok && !over()) setTimeout(loop, 0);
      else finish();
    };
    setTimeout(loop, 0);
    return 'started';
  };
  AP.stop = () => { AP.running = false; cc.director.calculateDeltaTime = origDt; cc.game.resume(); return 'stopped'; };
  return 'ready';
})();
