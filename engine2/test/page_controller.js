// Runs in the contest page https://suikagameweb.com/ko/ (the parent of the game iframe) and plays
// game after game with page_autoplay.js inside the iframe: reloads the iframe, waits until the
// game is ready, injects the agent, waits for the result screen, records, repeats.
//   CTRL.start({ target })  stop and keep the result screen when the shown score reaches target
//   CTRL.status(), CTRL.stop(), CTRL.export()  (export downloads every game with its moves as JSON)
// Records stay in this browser (localStorage 'ctrl.games'). Needs the Browser pane visible while a
// game loads (a hidden pane gives the canvas size 0 and a broken box).
(async () => {
  const BASE = 'https://raw.githubusercontent.com/jiwonsudo/supha-go/__SHA__/engine2/';
  const [s, a, p] = await Promise.all(['src/suika2.js', 'src/agent.js', 'test/page_autoplay.js'].map((f) => fetch(BASE + f).then((r) => r.text())));
  const code = p.split("load('./suika2', __SUIKA2_SRC__)").join("load('./suika2', " + JSON.stringify(s) + ')')
    .split("load('./agent', __AGENT_SRC__)").join("load('./agent', " + JSON.stringify(a) + ')');
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let saved = [];
  try { saved = JSON.parse(localStorage.getItem('ctrl.games') || '[]'); } catch (e) { saved = []; }
  const C = window.CTRL = { games: saved, running: false, phase: 'idle', target: null, error: null };
  const save = () => { try { localStorage.setItem('ctrl.games', JSON.stringify(C.games)); } catch (e) { /* full or blocked */ } };
  const frame = () => document.querySelector('#game_frame');

  async function ready(w) {
    for (let i = 0; i < 240; i++) {
      try {
        const gm = w.cc && w.cc.find && w.cc.find('Canvas/gameManager');
        if (w.cc.winSize.height > 1000 && gm && gm.getComponent('GameFunction').targetFruit) return true;
      } catch (e) { /* still loading */ }
      await sleep(500);
    }
    return false;
  }

  async function playOne() {
    const f = frame();
    if (!f.getAttribute('src')) document.querySelector('#loadGameButton')?.click();
    else f.contentWindow.location.reload();
    C.phase = 'loading';
    await sleep(2000);
    const w = f.contentWindow;
    if (!(await ready(w))) { C.error = 'game did not load (is the Browser pane visible?)'; return null; }
    C.phase = 'playing';
    w.eval(code);
    w.AP.start();
    while (w.AP.running) { await sleep(3000); C.moves = w.AP.moves; }
    const g = { ...w.AP.games[w.AP.games.length - 1], started: w.AP.started, error: w.AP.error || null, record: w.AP.record };
    C.games.push(g);
    save();
    return g;
  }

  C.start = async ({ target = null } = {}) => {
    if (C.running) return 'already running';
    C.running = true; C.target = target; C.error = null;
    (async () => {
      while (C.running) {
        let g = null;
        try { g = await playOne(); } catch (e) { C.error = String(e && e.stack); }
        if (!g) { await sleep(5000); continue; }
        if (target && (g.display || 0) >= target) { C.running = false; C.phase = 'stopped at target, result on screen'; break; }
      }
      if (C.phase === 'playing' || C.phase === 'loading') C.phase = 'idle';
    })();
    return 'started';
  };
  C.stop = () => { C.running = false; return 'will stop after this game'; };
  C.status = () => {
    const d = C.games.map((g) => g.display || 0);
    return { running: C.running, phase: C.phase, moves: C.moves, games: C.games.length, best: d.length ? Math.max(...d) : null,
      mean: d.length ? Math.round(d.reduce((x, y) => x + y, 0) / d.length) : null, last: C.games.slice(-5).map((g) => g.display), error: C.error };
  };
  C.export = () => {
    const blob = new Blob([JSON.stringify(C.games)], { type: 'application/json' });
    const el = document.createElement('a');
    el.href = URL.createObjectURL(blob);
    el.download = 'suphago-contest-games-' + new Date().toISOString().slice(0, 16).replace(/[:T]/g, '') + '.json';
    el.click();
  };
  return 'controller ready';
})();
