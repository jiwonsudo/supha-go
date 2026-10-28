'use strict';
// Headless Suika engine matching playsuikagame.com (Phaser 3.70.0 + its bundled Matter.js 0.19.0).
// Physics code is Phaser's own Matter build; game rules are re-implemented from observed behavior.

const LIB = 'phaser/src/physics/matter-js/lib';
const Engine = require(`${LIB}/core/Engine`);
const Events = require(`${LIB}/core/Events`);
const Common = require(`${LIB}/core/Common`);
const Composite = require(`${LIB}/body/Composite`);
const Body = require(`${LIB}/body/Body`);
const Bodies = require(`${LIB}/factory/Bodies`);
const Resolver = require(`${LIB}/collision/Resolver`);

// Resolver thresholds observed on the live page (library defaults are 2 and sqrt(6)).
Resolver._restingThresh = 4;
Resolver._restingThreshTangent = 6;

// Unscaled radius per fruit (Phaser setCircle radius before setScale(0.75)).
const BASE_RADIUS = [24.5, 31.5, 44, 48, 61, 78, 91, 111.5, 125.5, 154.5, 180];
const SCALE = 0.75;
const RADIUS = BASE_RADIUS.map((r) => r * SCALE);
const MERGE_SCORE = [1, 3, 6, 10, 15, 21, 28, 36, 45, 55, 66];
const MAX_TYPE = 10;
const SPAWN_TYPES = 5;

const WIDTH = 654;
const HEIGHT = 724;
const MARGIN_X = 55;
const MARGIN_BOTTOM = 16;
const WALL_THICKNESS = 100;
const DROP_Y = 80;
const GAMEOVER_Y = 70;
const FRAME_MS = 1000 / 60;
const COOLDOWN_MS = 600;

// mulberry32: small seeded PRNG standing in for Math.random. State lives on the
// game object so clone() can copy it.
function makeRngFromState(owner) {
  return function () {
    owner._rngState = (owner._rngState + 0x6d2b79f5) >>> 0;
    let t = owner._rngState;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

class SuikaGame {
  // displayHz: refresh rate of the original being emulated. Physics always steps
  // 1000/60 ms per frame; the 600ms drop cooldown is wall clock, so it spans
  // 36 frames at 60Hz and 72 frames at 120Hz.
  constructor({ seed = 0, displayHz = 60 } = {}) {
    this.displayHz = displayHz;
    this.cooldownFrames = Math.round((COOLDOWN_MS / 1000) * displayHz);
    this.reset(seed);
  }

  reset(seed = 0) {
    this._rngState = seed >>> 0;
    this.rng = makeRngFromState(this);
    this.engine = Engine.create({ gravity: { x: 0, y: 1.5, scale: 0.001 }, enableSleeping: false });
    this.world = this.engine.world;
    this.fruits = []; // live fruits: { type, body }
    this.score = 0;
    this.isOver = false;
    this.frame = 0;
    this._buildWalls();

    this._bindEvents();

    this.current = 0; // first fruit is always fruit0
    this.next = this._randomFruit();
    this.canDrop = true;
    this.cooldownLeft = 0;
    return this;
  }

  _bindEvents() {
    this.engine.events = {};
    Events.on(this.engine, 'collisionStart', (e) => {
      for (const pair of e.pairs) {
        // Phaser calls bodyA's then bodyB's onCollide callback; both run the same handler.
        if (pair.bodyA._fruit) this._onCollide(pair);
        if (pair.bodyB._fruit) this._onCollide(pair);
      }
    });
  }

  // Exact copy of the whole simulation (bodies, cached contacts, detector order, RNG)
  // so a search can branch from this state and get the same results as the original line.
  clone() {
    const c = Object.create(SuikaGame.prototype);
    const seen = new Map();
    const copy = (v) => {
      if (v === null || typeof v !== 'object') return v;
      if (seen.has(v)) return seen.get(v);
      const out = Array.isArray(v) ? new Array(v.length) : Object.create(Object.getPrototypeOf(v));
      seen.set(v, out);
      for (const k of Object.keys(v)) out[k] = copy(v[k]);
      return out;
    };
    const saved = this.engine.events;
    this.engine.events = {};
    c.engine = copy(this.engine);
    this.engine.events = saved;
    c.world = c.engine.world;
    c.fruits = copy(this.fruits);
    for (const k of ['displayHz', 'cooldownFrames', 'score', 'isOver', 'frame', 'current', 'next', 'canDrop', 'cooldownLeft']) c[k] = this[k];
    c._rngState = this._rngState;
    c.rng = makeRngFromState(c);
    c._bindEvents();
    return c;
  }

  _randomFruit() {
    return Math.floor(this.rng() * SPAWN_TYPES);
  }

  _buildWalls() {
    // Mirrors Phaser World.setBounds(55, 0, 544, 708, 100, true, true, true, true).
    const x = MARGIN_X, y = 0, w = WIDTH - MARGIN_X * 2, h = HEIGHT - MARGIN_BOTTOM, t = WALL_THICKNESS;
    const specs = [
      [x - t, y - t, t, h + t * 2],
      [x + w, y - t, t, h + t * 2],
      [x, y - t, w, t],
      [x, y + h, w, t],
    ];
    for (const [wx, wy, ww, wh] of specs) {
      const b = Bodies.rectangle(wx + ww / 2, wy + wh / 2, ww, wh, { isStatic: true, friction: 0, frictionStatic: 0 });
      b.friction = 1; // value observed on the live page
      Composite.add(this.world, b);
    }
  }

  _addFruit(type, x, y) {
    // Phaser matter.add.sprite first builds a rectangle body, then setCircle replaces it.
    Common.nextId();
    const body = Bodies.circle(x, y, BASE_RADIUS[type], {}, 25);
    body.friction = 1;
    body.restitution = 0;
    // Phaser setScale: Body.scale by 1/oldScale, then by new scale.
    Body.scale(body, 1, 1);
    Body.scale(body, SCALE, SCALE);
    const fruit = { type, body, alive: true };
    body._fruit = fruit;
    Composite.add(this.world, body);
    this.fruits.push(fruit);
    return fruit;
  }

  _destroy(fruit) {
    if (!fruit.alive) return;
    fruit.alive = false;
    fruit.body._fruit = null;
    Composite.remove(this.world, fruit.body, true);
    this.fruits.splice(this.fruits.indexOf(fruit), 1);
  }

  _onCollide(pair) {
    const fa = pair.bodyA._fruit, fb = pair.bodyB._fruit;
    if (!fa || !fb) return;
    if (fa.type === fb.type) {
      const type = fa.type;
      const px = pair.bodyA.position.x, py = pair.bodyA.position.y;
      this._destroy(fa);
      this._destroy(fb);
      this.score += MERGE_SCORE[type];
      if (type < MAX_TYPE) this._addFruit(type + 1, px, py);
    } else {
      const ya = pair.bodyA.position.y - pair.bodyA.centerOffset.y / 2;
      const yb = pair.bodyB.position.y - pair.bodyB.centerOffset.y / 2;
      if (ya < GAMEOVER_Y || yb < GAMEOVER_Y) this.isOver = true;
    }
  }

  // One display frame: one physics step, then the drop cooldown timer.
  stepFrame() {
    Engine.update(this.engine, FRAME_MS);
    this.frame++;
    if (!this.canDrop && !this.isOver) {
      this.cooldownLeft--;
      if (this.cooldownLeft <= 0) {
        this.current = this.next;
        this.next = this._randomFruit();
        this.canDrop = true;
      }
    }
  }

  // Drop the current fruit at x. Returns false if a drop is not allowed now.
  drop(x) {
    if (!this.canDrop || this.isOver) return false;
    this._addFruit(this.current, x, DROP_Y);
    this.canDrop = false;
    this.cooldownLeft = this.cooldownFrames;
    return true;
  }

  // Agent-level turn: drop at x, then run frames until the next drop is allowed
  // (plus optional extra waiting frames). Returns score gained this turn.
  turn(x, extraFrames = 0) {
    const before = this.score;
    if (!this.drop(x)) return 0;
    while (!this.canDrop && !this.isOver) this.stepFrame();
    for (let i = 0; i < extraFrames && !this.isOver; i++) this.stepFrame();
    return this.score - before;
  }

  // Build a game from a state read off a real page: fruits as
  // [type, x, y, vx, vy, angle, angularVelocity] (velocities per physics step, as
  // Matter stores them), plus current/next fruit and score. Contact caches and body
  // ids are not copied, so the first frames can differ slightly from the page.
  static fromState(s, { seed = 0, displayHz = 60, canDrop = true } = {}) {
    const g = new SuikaGame({ seed, displayHz });
    for (const f of s.fruits) {
      const [type, x, y, vx = 0, vy = 0, angle = 0, av = 0] = f;
      const fr = g._addFruit(type, x, y);
      Body.setAngle(fr.body, angle);
      Body.setVelocity(fr.body, { x: vx, y: vy });
      Body.setAngularVelocity(fr.body, av);
    }
    g.score = s.score || 0;
    g.current = s.current;
    g.next = s.next;
    g.canDrop = canDrop;
    g.isOver = false;
    return g;
  }

  state() {
    return {
      score: this.score,
      isOver: this.isOver,
      current: this.current,
      next: this.next,
      fruits: this.fruits.map((f) => [f.type, f.body.position.x, f.body.position.y, f.body.velocity.x, f.body.velocity.y, f.body.angle, f.body.angularVelocity]),
    };
  }
}

module.exports = { SuikaGame, RADIUS, BASE_RADIUS, MERGE_SCORE, WIDTH, HEIGHT, MARGIN_X, DROP_Y };
