'use strict';
// Headless engine for the contest site's game (suikagameweb.com/game/suikagame-ko.html):
// Cocos Creator 2.2.2 with its bundled Box2D (vendor/box2d.js, the same file as the engine's
// external/box2d/box2d.js). Rules re-implemented from the page's project.js (docs/contest-site.md).
//
// Coordinates: Cocos world space centred on the canvas, y up, px. The physics step is always
// 1/60 s per frame (enabledAccumulator is off, so Cocos steps 1/frameRate whatever the display
// does). Timers and tweens run on display time: `hz` frames per second.

const b2 = require('../vendor/box2d');

const PTM = 32;
const STEP = 1 / 60;
// Node height after setting the (trimmed) sprite frame; the collider radius is height / 2.
const DIAM = [52, 78, 108, 119, 152, 183, 186, 258, 308, 302, 404];
// Node width (the x clamp uses width / 2).
const WIDTH = [52, 78, 108, 119, 153, 183, 186, 258, 308, 302, 404];
const RADIUS = DIAM.map((d) => d / 2);
const MAX_TYPE = 10;
const SPAWN = [0, 0, 0, 1, 2, 2, 3]; // fixed opening fruits, then RandomInteger(0, 5) = 0..4
const RANDOM_TYPES = 5;

const LINE_NODE_Y = 491.357;        // lineNode / fruitNode y in the canvas
const FLOOR_TOP = -778 + 250;       // `down` box: centre -778, height 500
const WALL_X = 373, WALL_W = 25;    // left/right boxes: centre +-373, width 25, height 1280
const GRAVITY = -300;               // px/s^2, fruits use gravityScale 3
const DROP_SPEED = -800;            // px/s given to a dropped fruit
const MERGED_SPEED = -100;          // px/s given to a merged fruit

function rngFrom(owner) {
  return () => {
    owner._rngState = (owner._rngState + 0x6d2b79f5) >>> 0;
    let t = owner._rngState;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// cc.easing.backOut
function backOut(k) {
  const s = 1.70158;
  k -= 1;
  return k * k * ((s + 1) * k + s) + 1;
}

class SuikaGame2 {
  // winH: cc.winSize.height of the page (the dashed line and the drop height follow it; the
  //       canvas keeps width 720 and its height follows the window shape). hz: display rate.
  constructor({ seed = 0, hz = 60, winH = 1262.5 } = {}) {
    this.hz = hz;
    this.winH = winH;
    this.lineY = LINE_NODE_Y + winH / 2 - 680; // dashed line (game over above it)
    this.dropY = LINE_NODE_Y + winH / 2 - 580; // where the waiting fruit sits
    this.reset(seed);
  }

  f(sec) { return Math.round(sec * this.hz); }

  reset(seed = 0) {
    this._rngState = seed >>> 0;
    this.rng = rngFrom(this);
    this.world = new b2.b2World(new b2.b2Vec2(0, GRAVITY / PTM));
    this.fruits = [];
    this.score = 0;
    this.isOver = false;
    this.frame = 0;
    this.drops = 0;            // createFruitCount
    this.current = SPAWN[0];
    this.next = 0;
    this.canDrop = true;
    this.waitFrames = 0;       // frames until the next fruit can be dropped
    this.blockFrames = 0;      // frames of the watermelon animation (input off)
    this.pending = [];         // body changes queued during a step
    this.timers = [];          // [framesLeft, kind, data]
    this._buildWalls();
    this._bindListener();
    return this;
  }

  _buildWalls() {
    const box = (cx, cy, w, h, tag) => {
      const bd = new b2.b2BodyDef();
      bd.type = b2.b2BodyType.b2_staticBody;
      bd.position.Set(cx / PTM, cy / PTM);
      const body = this.world.CreateBody(bd);
      const sh = new b2.b2PolygonShape();
      sh.SetAsBox(w / 2 / PTM, h / 2 / PTM);
      const fd = new b2.b2FixtureDef();
      fd.shape = sh;
      fd.density = 1;
      fd.friction = 0.2;
      fd.restitution = 0;
      body.CreateFixture(fd).SetUserData(tag);
      return body;
    };
    this.walls = [box(-WALL_X, 0, WALL_W, 1280, 'wall'), box(WALL_X, 0, WALL_W, 1280, 'wall')];
    this.floor = box(0, -778, 720, 500, 'floor');
  }

  _bindListener() {
    const listener = new b2.b2ContactListener();
    listener.BeginContact = (contact) => this._beginContact(contact);
    this.world.SetContactListener(listener);
  }

  _newFruit(type, x, y, vy, scale) {
    const bd = new b2.b2BodyDef();
    bd.type = b2.b2BodyType.b2_dynamicBody;
    bd.position.Set(x / PTM, y / PTM);
    bd.linearVelocity.Set(0, vy / PTM);
    bd.gravityScale = 3;
    bd.allowSleep = true;
    const body = this.world.CreateBody(bd);
    const fr = {
      uid: this._uid = (this._uid || 0) + 1,
      type, body, fixture: null, scale, rad: RADIUS[type], alive: true,
      inBox: false, touched: false, merged: 0, boxTime: 0,
      numberUsed: 0, numberReset: -1, busy: false,
    };
    body.SetUserData(fr);
    this._setScale(fr, scale);
    this.fruits.push(fr);
    return fr;
  }

  // collider.apply(): rebuild the fixture with radius * scale (no fixture at scale 0)
  _setScale(fr, scale, radius = RADIUS[fr.type]) {
    fr.scale = scale;
    fr.rad = radius;
    if (fr.fixture) { fr.body.DestroyFixture(fr.fixture); fr.fixture = null; }
    if (scale === 0) return;
    const sh = new b2.b2CircleShape();
    sh.m_radius = (radius * scale) / PTM;
    const fd = new b2.b2FixtureDef();
    fd.shape = sh;
    fd.density = 1;
    fd.friction = 1;
    fd.restitution = 0.1;
    fr.fixture = fr.body.CreateFixture(fd);
    fr.fixture.SetUserData(fr);
  }

  _destroy(fr) {
    if (!fr.alive) return;
    fr.alive = false;
    this.world.DestroyBody(fr.body);
    this.fruits.splice(this.fruits.indexOf(fr), 1);
  }

  _beginContact(contact) {
    const a = contact.GetFixtureA().GetUserData();
    const b = contact.GetFixtureB().GetUserData();
    // Cocos calls onBeginContact on A's collider, then on B's.
    if (typeof a === 'object' && a) this._onContact(a, b);
    if (typeof b === 'object' && b) this._onContact(b, a);
  }

  // fruitData.onBeginContact(contact, self, other)
  _onContact(self, other) {
    if (typeof other !== 'object' || !other) { if (other === 'floor') self.inBox = true; return; }
    if (this.ignore && this.ignore.size) {
      // a rebuilt world (clone / fromState) re-reports contacts that already existed
      const key = self.uid < other.uid ? self.uid + ',' + other.uid : other.uid + ',' + self.uid;
      if (this.ignore.has(key)) { if (self.uid > other.uid) this.ignore.delete(key); return; }
    }
    other.touched = true; // (endCtrl is set on the fruit whose handler runs; both handlers run)
    self.touched = true;
    if (self.body.GetPosition().y < other.body.GetPosition().y) return;
    self.inBox = true;
    this.pending.push(() => self.alive && self.body.SetAngularVelocity(0));
    const t = self.type;
    if (t !== other.type || t > 9) return;
    self.merged += 1;
    // getNumber(): only the first call within 0.25 s returns 0
    const n = self.numberUsed++;
    self.numberReset = this.f(0.25);
    if (n !== 0 || self.busy || other.busy) return;
    self.busy = other.busy = true;
    this.score += t + 1;
    if (t === 9) this.blockFrames = this.f(0.1 + 3); // watermelon animation, +100 at the end
    this.pending.push(() => {
      this._setScale(self, self.scale, 0.0001);
      this._setScale(other, other.scale, 0.0001);
    });
    const p = other.body.GetPosition();
    this.timers.push({ left: this.f(0.1), kind: 'merge', self, other, from: { x: self.body.GetPosition().x, y: self.body.GetPosition().y }, to: { x: p.x, y: p.y }, total: this.f(0.1) });
  }

  stepFrame() {
    if (this.isOver) return;
    // component updates (fruitData.update): x clamp, game-over test
    for (const fr of this.fruits) {
      const p = fr.body.GetPosition();
      const lim = (360 - WIDTH[fr.type] / 2) / PTM;
      if (p.x < -lim || p.x > lim) fr.body.SetTransformXY(Math.max(-lim, Math.min(lim, p.x)), p.y, fr.body.GetAngle());
      if (fr.numberReset > 0 && --fr.numberReset === 0) fr.numberUsed = 0;
      if (fr.inBox) fr.boxTime += 1 / this.hz;
      if (p.y * PTM + WIDTH[fr.type] / 2 > this.lineY && fr.merged === 0 && fr.touched && fr.boxTime > 3) {
        this._gameOver();
        return;
      }
    }
    this.world.Step(STEP, 10, 10);
    this.ignore = null;
    const todo = this.pending; this.pending = [];
    for (const fn of todo) fn();
    this.frame++;
    this._runTimers();
    if (this.blockFrames > 0 && --this.blockFrames === 0) this.score += 100;
    if (!this.canDrop) {
      if (this.waitFrames > 0) this.waitFrames--;
      if (this.waitFrames === 0 && this.blockFrames === 0) this.canDrop = true;
    }
  }

  _runTimers() {
    const keep = [];
    for (const tm of this.timers) {
      tm.left--;
      if (tm.kind === 'merge') {
        if (!tm.self.alive || !tm.other.alive) continue;
        const k = 1 - tm.left / tm.total;
        tm.self.body.SetTransformXY(tm.from.x + (tm.to.x - tm.from.x) * k, tm.from.y + (tm.to.y - tm.from.y) * k, tm.self.body.GetAngle());
        if (tm.left > 0) { keep.push(tm); continue; }
        const p = tm.other.body.GetPosition();
        const type = tm.other.type + 1, x = p.x * PTM, y = p.y * PTM;
        this._destroy(tm.self);
        this._destroy(tm.other);
        if (this.merged) this.merged[type - 1]++;
        const fr = this._newFruit(type, x, y, MERGED_SPEED, 0);
        fr.inBox = true;
        keep.push({ left: this.f(0.5), kind: 'grow', fr, total: this.f(0.5) });
      } else if (tm.kind === 'grow') {
        if (!tm.fr.alive) continue;
        const k = 1 - tm.left / tm.total;
        this._setScale(tm.fr, tm.left > 0 ? backOut(k) : 1);
        if (tm.left > 0) keep.push(tm);
      }
    }
    this.timers = keep;
  }

  _gameOver() {
    this.isOver = true;
    // GameFunction.end(): every fruit left in the box adds its number + 1
    for (const fr of this.fruits) this.score += fr.type + 1;
  }

  _spawnNext() {
    this.current = this.next;
    this.drops++;
    this.next = this.drops < SPAWN.length - 1 ? SPAWN[this.drops + 1] : Math.floor(this.rng() * RANDOM_TYPES);
  }

  // Drop the current fruit at x (world px). The next one can be dropped 0.5 s (createOneFruit
  // delay) + 0.5 s (its scale-in tween) later.
  drop(x) {
    if (!this.canDrop || this.isOver) return false;
    const lim = 360 - WIDTH[this.current] / 2;
    x = Math.max(-lim, Math.min(lim, x));
    this._newFruit(this.current, x, this.dropY, DROP_SPEED, 1);
    this._spawnNext();
    this.canDrop = false;
    this.waitFrames = this.f(1.0);
    return true;
  }

  turn(x, extraFrames = 0) {
    const before = this.score;
    if (!this.drop(x)) return 0;
    while (!this.canDrop && !this.isOver) this.stepFrame();
    for (let i = 0; i < extraFrames && !this.isOver; i++) this.stepFrame();
    return this.score - before;
  }

  // Copy for search. Box2D's object graph does not survive a generic deep copy (memory blows
  // up after a few dozen copies), so the copy is a new world built from every body's position,
  // velocity and angle. Contact caches are lost, so a copy drifts slightly from the original.
  snapshot() {
    const idx = new Map(this.fruits.map((fr, i) => [fr, i]));
    return {
      g: { hz: this.hz, winH: this.winH, score: this.score, isOver: this.isOver, frame: this.frame, drops: this.drops,
        current: this.current, next: this.next, canDrop: this.canDrop, waitFrames: this.waitFrames,
        blockFrames: this.blockFrames, _rngState: this._rngState },
      fruits: this.fruits.map((fr) => {
        const p = fr.body.GetPosition(), v = fr.body.GetLinearVelocity();
        return { type: fr.type, x: p.x, y: p.y, vx: v.x, vy: v.y, a: fr.body.GetAngle(), av: fr.body.GetAngularVelocity(),
          scale: fr.scale, rad: fr.rad, inBox: fr.inBox, touched: fr.touched, merged: fr.merged, boxTime: fr.boxTime,
          numberUsed: fr.numberUsed, numberReset: fr.numberReset, busy: fr.busy, awake: fr.body.IsAwake() };
      }),
      timers: this.timers.map((tm) => (tm.kind === 'merge'
        ? { kind: 'merge', left: tm.left, total: tm.total, self: idx.get(tm.self), other: idx.get(tm.other), from: { ...tm.from }, to: { ...tm.to } }
        : { kind: 'grow', left: tm.left, total: tm.total, fr: idx.get(tm.fr) })).filter((tm) => (tm.kind === 'merge' ? tm.self !== undefined && tm.other !== undefined : tm.fr !== undefined)),
    };
  }

  static restore(snap) {
    const c = Object.create(SuikaGame2.prototype);
    Object.assign(c, snap.g);
    c.lineY = LINE_NODE_Y + c.winH / 2 - 680;
    c.dropY = LINE_NODE_Y + c.winH / 2 - 580;
    c.rng = rngFrom(c);
    c.world = new b2.b2World(new b2.b2Vec2(0, GRAVITY / PTM));
    c.fruits = [];
    c.pending = [];
    c._buildWalls();
    c._bindListener();
    for (const s of snap.fruits) {
      const fr = c._newFruit(s.type, s.x * PTM, s.y * PTM, 0, 0);
      fr.body.SetTransformXY(s.x, s.y, s.a);
      fr.body.SetLinearVelocity(new b2.b2Vec2(s.vx, s.vy));
      fr.body.SetAngularVelocity(s.av);
      c._setScale(fr, s.scale, s.rad);
      fr.body.SetAwake(s.awake);
      for (const k of ['inBox', 'touched', 'merged', 'boxTime', 'numberUsed', 'numberReset', 'busy']) fr[k] = s[k];
    }
    c.ignore = new Set();
    const fs = c.fruits;
    for (let i = 0; i < fs.length; i++) {
      for (let j = i + 1; j < fs.length; j++) {
        const a = fs[i], b = fs[j];
        const pa = a.body.GetPosition(), pb = b.body.GetPosition();
        if (Math.hypot(pa.x - pb.x, pa.y - pb.y) * PTM <= a.rad * a.scale + b.rad * b.scale + 2) c.ignore.add(Math.min(a.uid, b.uid) + ',' + Math.max(a.uid, b.uid));
      }
    }
    c.timers = snap.timers.map((tm) => (tm.kind === 'merge'
      ? { ...tm, self: fs[tm.self], other: fs[tm.other] }
      : { ...tm, fr: fs[tm.fr] }));
    return c;
  }

  clone() {
    return SuikaGame2.restore(this.snapshot());
  }

  // State in y-down "box" coordinates: X = x + 360 (walls at 0 and 720), Y = lineY - y + 100
  // is not used; Y = 640 - y keeps the drop height and line fixed for a given winH.
  state() {
    return {
      score: this.score,
      isOver: this.isOver,
      current: this.current,
      next: this.next,
      fruits: this.fruits.map((fr) => {
        const p = fr.body.GetPosition(), v = fr.body.GetLinearVelocity();
        return [fr.type, p.x * PTM + 360, 640 - p.y * PTM, v.x * PTM / 60, -v.y * PTM / 60, -fr.body.GetAngle(), fr.body.GetAngularVelocity()];
      }),
    };
  }
}

module.exports = { SuikaGame2, RADIUS, DIAM, WIDTH, MAX_TYPE, PTM };
