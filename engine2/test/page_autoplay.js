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
  let frames = 0;
  const step = () => { frames++; cc.director.mainLoop(performance.now()); };
  const fixedDt = function () { this._deltaTime = 1 / 60; };
  const origDt = cc.director.calculateDeltaTime;
  // Cocos resumes the game by itself when the page becomes visible again (cc.game EVENT_SHOW).
  // While the AI steps frames by hand that would run the game twice, so resume is blocked
  // until the game is over.
  const origResume = cc.game.resume.bind(cc.game);
  const hold = () => { cc.game.resume = () => {}; cc.game.pause(); };
  const release = () => { cc.game.resume = origResume; cc.director.calculateDeltaTime = origDt; origResume(); };

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

  const AP = window.AP = { games: [], moves: 0, running: false, opts: { n: 50, chain: 2, inv: 0.6 }, log: [], record: [], diag: [] };
  AP.status = () => ({ running: AP.running, moves: AP.moves, score: PI.score, over: over(), games: AP.games });

  function move() {
    const g0 = gf();
    let guard = 0;
    while ((!g0.targetFruit || !PI.playerTouch) && !over() && guard++ < 1200) step();
    if (over()) return false;
    let w = 0, fs = read();
    while (!calm(fs) && !over() && w++ < 900) { step(); fs = read(); }
    if (over() || !g0.targetFruit) return !over();
    // diagnostics: how did the engine's forecast of the previous move compare with what happened?
    if (AP.pending) {
      const pr = AP.pending; AP.pending = null;
      const sim = pr.g; for (let k = 0; k < frames - pr.f0; k++) sim.stepFrame();
      const cnt = (arr) => { const c = new Array(11).fill(0); for (const f of arr) c[f.type]++; return c; };
      const a = cnt(fs), b = cnt(sim.fruits);
      AP.diag.push({ m: AP.moves, frames: frames - pr.f0, real: fs.length, pred: sim.fruits.length, same: a.join() === b.join(), simOver: sim.isOver });
    }
    const cur = g0.targetFruit.getComponent('fruitData').fruitNumber;
    const g = SuikaGame2.restore({
      g: { hz: 60, winH: cc.winSize.height, score: 0, isOver: false, frame: 0, drops: 10, current: cur, next: (0, eval)('next'), canDrop: true,
        waitFrames: 0, blockFrames: 0, _rngState: (rng() * 4294967296) >>> 0 },
      fruits: fs, timers: [],
    });
    const t0 = performance.now();
    const c = chooseMove(g, rng, AP.opts);
    const fc = g.clone(); fc.drop(c.x); AP.pending = { g: fc, f0: frames };
    g0.targetFruit.x = Math.max(-360 + 1, Math.min(360 - 1, c.x));
    ic().touchNum = 1;
    ic().onTouchEnd({});
    AP.moves++;
    AP.log.push({ m: AP.moves, cur, x: +c.x.toFixed(1), best: c.best, ms: Math.round(performance.now() - t0), score: PI.score });
    // whole-game record (evidence): move, current, next, drop x (canvas px), score before, fruits on the board
    const tc = new Array(11).fill(0); for (const f of fs) tc[f.type]++;
    AP.record.push([AP.moves, cur, g.next, +c.x.toFixed(1), PI.score, fs.length, tc.join('')]);
    AP.lastBoard = fs.map((f) => [f.type, +(f.x * PTM).toFixed(1), +(f.y * PTM).toFixed(1)]);
    if (AP.log.length > 50) AP.log.shift();
    return true;
  }

  function finish() {
    // let the page run normally: end() adds the end bonus with real-time timeouts, then shows the result
    // what the board looked like at game over, and whether the engine saw it coming
    const fsOver = read();
    const lastBoard = AP.lastBoard;
    const endInfo = { bonus: fsOver.reduce((t, f) => t + f.type + 1, 0), board: fsOver.map((f) => [f.type, +(f.x * PTM).toFixed(1), +(f.y * PTM).toFixed(1), f.inBox ? 1 : 0, f.touched ? 1 : 0]),
      lastLog: AP.log.slice(-5), lineY: cc.find('Canvas/lineNode') && cc.find('Canvas/lineNode').y, lastBoard };
    if (AP.pending) {
      const pr = AP.pending; const sim = pr.g; const n = frames - pr.f0;
      for (let k = 0; k < n + 240 && !sim.isOver; k++) sim.stepFrame();
      endInfo.forecast = { framesReal: n, simOver: sim.isOver, simFrame: sim.frame, simFruits: sim.fruits.length };
    }
    AP.endInfo = endInfo;
    release();
    const startScore = PI.score;
    setTimeout(() => {
      const shown = document.getElementById('ThisGameScoreResult');
      AP.games.push({ end: new Date().toISOString(), moves: AP.moves, scoreAtOver: startScore, final: PI.score,
        display: shown ? +(shown.textContent || '').trim() || null : null, winH: cc.winSize.height, opts: AP.opts, resumed: AP.resumed || 0, endInfo });
      try { localStorage.setItem('AP.games', JSON.stringify(AP.games)); } catch (e) { /* storage may be blocked */ }
      AP.running = false;
    }, 15000);
  }

  AP.start = () => {
    if (AP.running) return 'already running';
    AP.running = true;
    AP.moves = 0;
    AP.record = [];
    AP.diag = [];
    AP.pending = null;
    AP.started = new Date().toISOString();
    hold();
    cc.director.calculateDeltaTime = fixedDt;
    // setTimeout is throttled in a hidden page (down to once a minute), so the next move is
    // scheduled through a MessageChannel, which is not throttled.
    const mc = new MessageChannel();
    const next = (fn) => { mc.port1.onmessage = fn; mc.port2.postMessage(0); };
    const loop = () => {
      if (!AP.running) return;
      if (!cc.game.isPaused()) { AP.resumed = (AP.resumed || 0) + 1; cc.game.pause(); }
      let ok = true;
      try { ok = move(); } catch (e) { AP.error = String(e && e.stack); ok = false; }
      if (ok && !over()) next(loop);
      else finish();
    };
    next(loop);
    return 'started';
  };
  AP.stop = () => { AP.running = false; release(); return 'stopped'; };
  return 'ready';
})();
