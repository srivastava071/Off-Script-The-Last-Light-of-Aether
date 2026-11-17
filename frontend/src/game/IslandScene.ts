import Phaser from "phaser";

import type { BeliefFact, CharacterView, LocationView, StateView } from "../types/api";
import type { Bubble } from "./bubbles";
import {
  characterPosition, controlPoint, pointOnCurve, projectedSimTime, ROUTE_BEND, sampleCurve, type Point,
} from "./geometry";
import { paintScenery } from "./scenery";

/** Mind View on the map: one character's picture of the island, drawn over the real one. */
export interface MindOverlay {
  name: string;
  beliefs: BeliefFact[];
}

export interface MapFrame {
  state: StateView;
  receivedAt: number;
  focus: string | null;
  mind?: MindOverlay | null;
}

const W = 1000;
const H = 700;
const FONT = "Fredoka, 'Comic Sans MS', 'Segoe UI', sans-serif";
const INK = 0x1d2142;
const TOON = 1.65; // character size
const BUBBLE_LIFT = 112; // bubble distance above a character's feet
const RES = 2; // render at twice the world size so the map stays crisp on large and high-DPI screens

const C = {
  sea: 0x4cc9f0,
  seaLight: 0x7ad7f5,
  sand: 0xffd98e,
  grass: 0x8bd96b,
  grassDark: 0x6cc24a,
  path: 0xf7dfa8,
  broken: 0xff6b6b,
  locked: 0xb08968,
  flooded: 0x339af0,
  crystal: 0xffe066,
  gateOpen: 0x63e6be,
  trunk: 0x9c6644,
  leaf: 0x51cf66,
  leafDark: 0x2f9e44,
  rock: 0xb7bec7,
  skin: 0xffd8b1,
  pants: 0x495057,
  cheek: 0xff8fab,
};

const MIND = 0x7048e8; // Mind View: what a character believes
const hex = (color: string) => Phaser.Display.Color.HexStringToColor(color).color;

const COAST: [number, number][] = [
  [70, 210], [120, 110], [260, 95], [400, 130], [560, 95], [720, 120], [860, 85], [950, 160], [955, 300],
  [900, 420], [930, 540], [820, 640], [640, 655], [470, 625], [330, 660], [170, 650], [80, 560], [100, 420],
  [55, 320],
];
/** Where each place's name sits, relative to the place, so labels clear the landmark and the characters. */
const LABEL_OFFSET: Record<string, [number, number]> = {
  lighthouse: [0, -112],
  harbour: [-30, -120],
  bridge: [-6, -44],
  forest: [0, -100],
  temple: [0, -96],
  chamber: [0, -62],
};
const RAVINE: [number, number][] = [[546, 668], [572, 562], [562, 472], [590, 382], [612, 296], [654, 296],
  [640, 386], [620, 472], [632, 562], [608, 668]];

// Small emoji "thought icons" shown above a character while they work.
const ACTIVITY_EMOJI: Record<string, string> = {
  repair_bridge: "🔨", repair_mechanism: "⚙️", repair_lighthouse: "🔧", decode_symbols: "📜", pull_lever: "🕹️",
  discover_route: "🔍", detect_traps: "⚠️", block_route: "🪵", clear_route: "🧹", install_crystal: "💎",
  activate_lighthouse: "💡", signal: "📯", inspect: "👀", pick_up: "✋", drop: "✋", give: "🤝", talk: "💬", ask: "❓",
  request_help: "🙏",
};

type Mood = "happy" | "worried" | "surprised";

interface Toon {
  root: Phaser.GameObjects.Container;
  art: Phaser.GameObjects.Container; // flips left/right; text stays outside it
  legs: Phaser.GameObjects.Graphics;
  arms: Phaser.GameObjects.Graphics;
  face: Phaser.GameObjects.Graphics;
  ring: Phaser.GameObjects.Ellipse;
  focus: Phaser.GameObjects.Ellipse;
  emoji: Phaser.GameObjects.Container;
  emojiText: Phaser.GameObjects.Text;
  crystal: Phaser.GameObjects.Star;
  you: Phaser.GameObjects.Container | null;
  id: string;
  phase: number;
  lastX: number;
  lastY: number;
  moving: boolean;
  mood: Mood;
  surprisedUntil: number;
  nextBlink: number;
  bubble: Phaser.GameObjects.Container | null;
}

export class IslandScene extends Phaser.Scene {
  private frame: MapFrame | null = null;
  private ready = false;
  private routeLayer!: Phaser.GameObjects.Graphics;
  private siteLayer!: Phaser.GameObjects.Graphics;
  private beam!: Phaser.GameObjects.Graphics;
  private storm!: Phaser.GameObjects.Rectangle;
  private rain: Phaser.GameObjects.Particles.ParticleEmitter | null = null;
  private looseCrystal!: Phaser.GameObjects.Star;
  private crystalMark!: Phaser.GameObjects.Container;
  private goalBanner!: Phaser.GameObjects.Container;
  private stormBank!: Phaser.GameObjects.Container;
  private bolt!: Phaser.GameObjects.Graphics;
  private nextBolt = 0;
  private toons = new Map<string, Toon>();
  private drawnKey = "";
  private mindLayer!: Phaser.GameObjects.Container;
  private mindKey = "";
  private nextLightning = 0;
  private celebrated = false;
  onSelect: (id: string) => void = () => {};

  constructor() {
    super("island");
  }

  create(): void {
    this.cameras.main.setZoom(RES).centerOn(W / 2, H / 2);
    this.makeTextures();
    this.drawStatic();
    this.routeLayer = this.add.graphics().setDepth(2);
    this.siteLayer = this.add.graphics().setDepth(3);
    this.beam = this.add.graphics().setDepth(4);
    this.looseCrystal = this.add.star(0, 0, 5, 5, 11, C.crystal).setStrokeStyle(2.5, INK).setVisible(false).setDepth(6);
    this.tweens.add({ targets: this.looseCrystal, angle: 360, duration: 4000, repeat: -1 });
    this.tweens.add({ targets: this.looseCrystal, scale: 1.2, yoyo: true, repeat: -1, duration: 600 });
    this.storm = this.add.rectangle(W / 2, H / 2, W, H, INK, 0).setDepth(30);

    // A soft glow and a name tag mark the Sun Crystal wherever it lies.
    const glow = this.add.circle(0, 0, 22, C.crystal, 0.45);
    this.tweens.add({ targets: glow, scale: 1.9, alpha: 0, duration: 1400, repeat: -1, ease: "Sine.out" });
    const tag = this.add.container(0, 34);
    this.setPill(tag, "Sun Crystal", 0xfff3bf);
    this.crystalMark = this.add.container(0, 0, [glow, tag]).setDepth(5).setVisible(false);
    this.goalBanner = this.add.container(0, 0).setDepth(9).setVisible(false);
    this.tweens.add({ targets: this.goalBanner, scale: 1.07, yoyo: true, repeat: -1, duration: 900, ease: "Sine.inOut" });

    this.stormBank = this.makeStormBank();
    this.mindLayer = this.add.container(0, 0).setDepth(12);
    this.ready = true;
    if (this.frame) this.render(this.frame);
  }

  setFrame(frame: MapFrame): void {
    this.frame = frame;
    if (this.ready) this.render(frame);
  }

  // --- textures for particles ---------------------------------------------------------------------------

  private makeTextures(): void {
    const g = this.make.graphics({ x: 0, y: 0 }, false);
    g.fillStyle(0xffffff).fillRect(0, 0, 6, 10).generateTexture("confetti", 6, 10).clear();
    g.fillStyle(0xffffff).fillCircle(6, 6, 6).generateTexture("dot", 12, 12).clear();
    g.fillStyle(0xbfe7ff).fillRect(0, 0, 2, 14).generateTexture("raindrop", 2, 14).clear();
    g.fillStyle(0xffffff);
    const pts: Phaser.Types.Math.Vector2Like[] = [];
    for (let i = 0; i < 10; i++) {
      const r = i % 2 ? 4 : 10;
      const a = (i / 10) * Math.PI * 2 - Math.PI / 2;
      pts.push({ x: 10 + Math.cos(a) * r, y: 10 + Math.sin(a) * r });
    }
    g.fillPoints(pts, true).generateTexture("star", 20, 20).destroy();
  }

  // --- static scenery -------------------------------------------------------------------------------------

  private drawStatic(): void {
    // Sea, island, canyon and mountains are painted once onto a canvas (gradients, soft shadows).
    const coast = new Phaser.Curves.Spline(COAST.flatMap(([x, y]) => [x, y]).concat(COAST[0]));
    const pts = coast.getPoints(160).map((p) => ({ x: p.x, y: p.y }));
    if (!this.textures.exists("scenery")) {
      const tex = this.textures.createCanvas("scenery", W * RES, H * RES);
      if (tex) {
        tex.getContext().scale(RES, RES);
        paintScenery(tex.getContext(), W, H, pts, RAVINE.map(([x, y]) => ({ x, y })));
        tex.refresh();
      }
    }
    this.add.image(0, 0, "scenery").setOrigin(0).setScale(1 / RES).setDepth(0);

    // The Whispering Forest: a dense ring of round trees, a few strays, and pines by the mountains.
    for (let i = 0; i < 22; i++) {
      const a = (i / 22) * Math.PI * 2;
      const r = 58 + (i % 3) * 22;
      this.tree(450 + Math.cos(a) * r * 1.45, 232 + Math.sin(a) * r * 0.72, 0.85 + (i % 3) * 0.14, i);
    }
    for (const [x, y] of [[300, 330], [355, 425], [250, 470], [690, 560], [790, 520], [235, 300]]) this.tree(x, y, 0.78, x);
    for (const [x, y, s] of [[660, 320, 0.8], [930, 420, 0.75], [700, 470, 0.7], [950, 300, 0.7]] as const) this.pine(x, y, s);

    // The boat that brought the team, moored at the end of the pier.
    const boat = this.add.graphics();
    const hull = [{ x: -30, y: 0 }, { x: 30, y: 0 }, { x: 20, y: 15 }, { x: -20, y: 15 }];
    boat.fillStyle(0x000000, 0.18).fillEllipse(0, 18, 64, 10);
    boat.fillStyle(0xe8590c).fillPoints(hull, true).lineStyle(3, INK).strokePoints(hull, true);
    boat.fillStyle(0xffffff).fillRect(-26, 3, 52, 3);
    boat.lineStyle(3, INK).lineBetween(0, 0, 0, -34);
    boat.fillStyle(0xffffff).fillTriangle(2, -32, 2, -4, 24, -6).lineStyle(2.5, INK).strokeTriangle(2, -32, 2, -4, 24, -6);
    boat.fillStyle(0xff6b6b).fillTriangle(0, -34, 0, -26, -10, -30);
    const boatC = this.add.container(268, 662, [boat]).setDepth(2);
    this.tweens.add({ targets: boatC, y: 655, angle: 4, yoyo: true, repeat: -1, duration: 1400, ease: "Sine.inOut" });

    // Little white waves.
    for (let i = 0; i < 18; i++) {
      const wx = 30 + ((i * 263) % 940);
      const wy = i % 2 ? 22 + ((i * 47) % 40) : 670 + ((i * 31) % 22);
      const wave = this.add.arc(wx, wy, 9, 200, 340, false).setStrokeStyle(3, 0xffffff, 0.9).setDepth(1);
      this.tweens.add({ targets: wave, alpha: 0.15, x: wx + 16, yoyo: true, repeat: -1, duration: 1800 + i * 120 });
    }

    // Small clouds drifting along the top edge, high above the labels.
    for (let i = 0; i < 3; i++) this.cloud(i * 380 - 100, i % 2 ? 22 : 40, 0.55 + (i % 2) * 0.15, 52000 + i * 11000);
  }

  /** The storm wall: dark clouds that creep in from the east as the deadline approaches (a clock you can see). */
  private makeStormBank(): Phaser.GameObjects.Container {
    const g = this.add.graphics();
    g.fillStyle(0x343a40, 0.94).fillRect(46, -30, 420, H + 60);
    for (let y = -30, i = 0; y < H + 40; y += 44, i++) {
      const x = i % 2 ? 18 : 0;
      g.fillStyle(INK).fillCircle(x, y, 41);
      g.fillStyle(i % 3 === 0 ? 0x5c677d : 0x495057).fillCircle(x, y, 38);
      g.fillStyle(0x6c7a93, 0.6).fillCircle(x - 10, y - 12, 14);
    }
    for (let k = 0; k < 40; k++) {
      const rx = 40 + ((k * 53) % 300);
      const ry = (k * 97) % H;
      g.lineStyle(2, 0xbfe7ff, 0.5).lineBetween(rx, ry, rx - 6, ry + 18);
    }
    this.bolt = this.add.graphics().setVisible(false);
    const bank = this.add.container(W + 200, 0, [g, this.bolt]).setDepth(28);
    this.tweens.add({ targets: g, y: 6, yoyo: true, repeat: -1, duration: 2600, ease: "Sine.inOut" });
    return bank;
  }

  private tree(x: number, y: number, s: number, seed: number): void {
    const g = this.add.graphics();
    g.fillStyle(0x000000, 0.18).fillEllipse(5 * s, 16 * s, 36 * s, 10 * s);
    g.fillStyle(INK).fillRoundedRect(-5 * s, -6 * s, 10 * s, 23 * s, 3 * s);
    g.fillStyle(C.trunk).fillRoundedRect(-3 * s, -4 * s, 6 * s, 19 * s, 2 * s);
    const base = [0x40c057, 0x51cf66, 0x37b24d][seed % 3];
    const blobs: [number, number, number][] = [[-10, -18, 13], [10, -19, 13], [0, -31, 15]];
    for (const [bx, by, r] of blobs) g.fillStyle(INK).fillCircle(bx * s, by * s, (r + 2.6) * s);
    for (const [bx, by, r] of blobs) g.fillStyle(base).fillCircle(bx * s, by * s, r * s);
    g.fillStyle(0x2b8a3e, 0.45).fillCircle(7 * s, -15 * s, 9 * s).fillCircle(-6 * s, -13 * s, 6 * s);
    g.fillStyle(0xffffff, 0.4).fillCircle(-5 * s, -35 * s, 5 * s).fillCircle(-13 * s, -22 * s, 3 * s);
    const t = this.add.container(x, y, [g]).setDepth(1);
    this.tweens.add({ targets: t, angle: { from: -2.5, to: 2.5 }, yoyo: true, repeat: -1, duration: 1700 + (seed % 5) * 220,
      ease: "Sine.inOut" });
  }

  private pine(x: number, y: number, s: number): void {
    const g = this.add.graphics();
    g.fillStyle(0x000000, 0.18).fillEllipse(4 * s, 12 * s, 30 * s, 8 * s);
    g.fillStyle(INK).fillRect(-4 * s, -4 * s, 8 * s, 16 * s).fillStyle(C.trunk).fillRect(-2 * s, -3 * s, 4 * s, 14 * s);
    for (const [ty, hw] of [[-4, 20], [-20, 16], [-34, 11]] as const) {
      const tri = [{ x: -hw * s, y: ty * s }, { x: hw * s, y: ty * s }, { x: 0, y: (ty - 24) * s }];
      g.fillStyle(0x2b8a3e).fillPoints(tri, true).lineStyle(2.5, INK).strokePoints(tri, true);
      g.fillStyle(0x51cf66, 0.6).fillTriangle(-hw * 0.6 * s, (ty - 3) * s, 0, (ty - 21) * s, -2 * s, (ty - 3) * s);
    }
    const t = this.add.container(x, y, [g]).setDepth(1);
    this.tweens.add({ targets: t, angle: { from: -1.5, to: 1.5 }, yoyo: true, repeat: -1, duration: 2100, ease: "Sine.inOut" });
  }

  private cloud(x: number, y: number, s: number, duration: number): void {
    const g = this.add.graphics();
    const puffs: [number, number, number][] = [[0, 0, 22], [24, -8, 26], [50, 0, 20], [26, 8, 22]];
    for (const [px, py, r] of puffs) g.fillStyle(INK).fillCircle(px * s, py * s, (r + 3) * s);
    for (const [px, py, r] of puffs) g.fillStyle(0xffffff).fillCircle(px * s, py * s, r * s);
    g.fillStyle(0xd0ebff).fillCircle(30 * s, 10 * s, 14 * s);
    const c = this.add.container(x, y, [g]).setDepth(7).setAlpha(0.92); // below the place labels
    this.tweens.add({ targets: c, x: W + 120, duration, repeat: -1, onRepeat: () => c.setX(-120) });
  }

  // --- dynamic layers ---------------------------------------------------------------------------------------

  private render(frame: MapFrame): void {
    const { state } = frame;
    const key = JSON.stringify([state.routes, state.temple_lock, state.lighthouse, state.flood]);
    if (key !== this.drawnKey) {
      this.drawnKey = key;
      this.drawRoutes(state);
      this.drawSites(state);
    }
    const mindKey = frame.mind ? JSON.stringify([frame.mind.name, frame.mind.beliefs.filter((b) => !b.up_to_date)]) : "";
    if (mindKey !== this.mindKey) {
      this.mindKey = mindKey;
      this.drawMind(state, frame.mind ?? null);
    }
    for (const c of state.characters) if (!this.toons.has(c.id)) this.toons.set(c.id, this.makeToon(c));
    for (const c of state.characters) {
      const t = this.toons.get(c.id)!;
      t.ring.setVisible(!c.autonomous);
      t.focus.setVisible(frame.focus === c.id);
      const working = !c.travel && c.activity && c.activity.type !== "wait" ? ACTIVITY_EMOJI[c.activity.type] : undefined;
      t.emoji.setVisible(!!working);
      if (working) t.emojiText.setText(working);
      t.crystal.setVisible(c.inventory.includes("sun_crystal"));
      t.mood = c.plan && (c.plan.status === "blocked" || c.plan.status === "failed") ? "worried" : "happy";
    }
    if (state.lighthouse.activated && !this.celebrated) {
      this.celebrated = true;
      const lh = state.locations.find((l) => l.id === "lighthouse");
      if (lh) this.confetti(lh.x, lh.y - 40);
    }
  }

  /** Mind View: a thought bubble on every road the character is wrong about, and a ghost wherever it
   *  wrongly thinks a teammate or an item is. Only facts the player can already see are compared. */
  private drawMind(state: StateView, mind: MindOverlay | null): void {
    this.mindLayer.removeAll(true);
    if (!mind) return;
    const wrong = mind.beliefs.filter((b) => !b.up_to_date);
    const loc = new Map(state.locations.map((l) => [l.id, l]));
    const items: Phaser.GameObjects.GameObject[] = [this.add.rectangle(W / 2, H / 2, W, H, MIND, 0.1)];

    const bubble = (x: number, y: number, label: string) => {
      const text = this.add.text(0, 0, label, { fontFamily: FONT, resolution: RES, fontSize: "12px", color: "#1d2142", fontStyle: "bold" })
        .setOrigin(0.5);
      const w = text.width + 18;
      const g = this.add.graphics();
      g.fillStyle(INK).fillRoundedRect(-w / 2, -10, w, 23, 11.5);
      g.fillStyle(0xf3f0ff).fillRoundedRect(-w / 2, -13, w, 23, 11.5).lineStyle(2.5, MIND).strokeRoundedRect(-w / 2, -13, w, 23, 11.5);
      g.fillStyle(0xf3f0ff).lineStyle(2, MIND).fillCircle(-4, 18, 4).strokeCircle(-4, 18, 4).fillCircle(-9, 26, 2.5).strokeCircle(-9, 26, 2.5);
      const c = this.add.container(x, y, [g, text]);
      this.tweens.add({ targets: c, y: y - 4, yoyo: true, repeat: -1, duration: 1300, ease: "Sine.inOut" });
      return c;
    };

    for (const f of wrong.filter((b) => b.kind === "route" && b.route_id)) {
      const r = state.routes.find((x) => x.id === f.route_id);
      const a = r && loc.get(r.a);
      const b = r && loc.get(r.b);
      if (!r || !a || !b) continue;
      const mid = pointOnCurve(a, b, ROUTE_BEND[r.id] ?? 0, 0.5);
      items.push(bubble(mid.x, mid.y - 34, `${mind.name} thinks: ${f.believed}`));
    }

    // Ghosts: where the character believes teammates and items are (when that is wrong).
    const perPlace = new Map<string, number>();
    for (const f of wrong.filter((b) => (b.kind === "teammate" || b.kind === "item") && b.believed_location)) {
      const at = loc.get(f.believed_location!);
      if (!at) continue;
      const n = perPlace.get(at.id) ?? 0;
      perPlace.set(at.id, n + 1);
      // Beside the place (above it near the south coast, where the map key and the sea are).
      const x = at.x + 52 + n * 48;
      const y = at.y > 500 ? at.y - 20 : at.y + 34;
      const g = this.add.graphics();
      if (f.kind === "teammate") {
        g.fillStyle(MIND, 0.3).fillCircle(0, 0, 19).lineStyle(3, MIND, 0.95).strokeCircle(0, 0, 19);
        g.fillStyle(0xffffff, 0.9).fillCircle(-6, -3, 3.5).fillCircle(6, -3, 3.5);
      } else {
        const d = [{ x: 0, y: -15 }, { x: 13, y: 0 }, { x: 0, y: 15 }, { x: -13, y: 0 }];
        g.fillStyle(MIND, 0.3).fillPoints(d, true).lineStyle(3, MIND, 0.95).strokePoints(d, true);
      }
      const label = this.add.text(0, 29, `${f.subject.split(" ")[0]}?`,
        { fontFamily: FONT, resolution: RES, fontSize: "13px", color: "#5f3dc4", fontStyle: "bold" })
        .setOrigin(0.5).setStroke("#ffffff", 4);
      const ghost = this.add.container(x, y, [g, label]).setAlpha(0.9);
      this.tweens.add({ targets: ghost, alpha: 0.45, yoyo: true, repeat: -1, duration: 1100, ease: "Sine.inOut" });
      items.push(ghost);
    }

    const title = this.add.container(W / 2, 24);
    this.setPill(title, wrong.some((b) => b.kind !== "teammate")
      ? `${mind.name}'s picture of the island · ${wrong.filter((b) => b.kind !== "teammate").length} out of date`
      : `${mind.name}'s picture of the island matches reality`, 0xe5dbff, false);
    items.push(title);
    this.mindLayer.add(items);
  }

  private drawRoutes(state: StateView): void {
    const g = this.routeLayer.clear();
    const loc = new Map(state.locations.map((l) => [l.id, l]));
    for (const r of state.routes) {
      const a = loc.get(r.a);
      const b = loc.get(r.b);
      if (!a || !b) continue;
      const bend = ROUTE_BEND[r.id] ?? 0;
      const pts = sampleCurve(a, b, bend, 30);
      const color = r.status === "broken" ? C.broken : r.status === "locked" ? C.locked
        : r.status === "flooded" ? C.flooded : C.path;
      const dashed = r.status !== "open" || !!r.requires_ability;
      g.lineStyle(14, INK, 1);
      this.stroke(g, pts, dashed, r.status === "broken");
      g.lineStyle(9, color, 1);
      this.stroke(g, pts, dashed, r.status === "broken");
      if (!dashed) {
        g.lineStyle(2, 0xffffff, 0.55); // sunlit centre of the trail
        this.stroke(g, pts.map((p) => ({ x: p.x - 1, y: p.y - 1.5 })), true);
      }
      if (r.id === "main_bridge") this.ropeBridge(g, sampleCurve(a, b, bend, 80), r.status === "open");

      const mid = pointOnCurve(a, b, bend, 0.5);
      if (r.status === "broken") this.sign(g, mid, "✕");
      if (r.obstructed) this.barricade(g, mid);
      if (r.status === "locked") this.padlock(g, mid);
      if (r.hazard) {
        for (const t of [0.3, 0.5, 0.7]) {
          const p = pointOnCurve(a, b, bend, t);
          if (r.hazard_active) {
            g.fillStyle(0xffd43b).fillTriangle(p.x - 8, p.y + 6, p.x, p.y - 8, p.x + 8, p.y + 6);
            g.lineStyle(2.5, INK).strokeTriangle(p.x - 8, p.y + 6, p.x, p.y - 8, p.x + 8, p.y + 6);
          } else {
            g.lineStyle(2.5, INK).lineBetween(p.x, p.y + 6, p.x, p.y - 12);
            g.fillStyle(0x40c057).fillTriangle(p.x, p.y - 12, p.x + 10, p.y - 8, p.x, p.y - 4);
          }
        }
      }
    }
  }

  private stroke(g: Phaser.GameObjects.Graphics, pts: Point[], dashed: boolean, gapInMiddle = false): void {
    for (let i = 0; i < pts.length - 1; i++) {
      if (dashed && i % 2 === 1) continue;
      if (gapInMiddle && i > pts.length * 0.4 && i < pts.length * 0.6) continue;
      g.lineBetween(pts[i].x, pts[i].y, pts[i + 1].x, pts[i + 1].y);
    }
  }

  /** Planks and ropes where the Main Bridge crosses the canyon; a gap in the middle while it is broken. */
  private ropeBridge(g: Phaser.GameObjects.Graphics, pts: Point[], whole: boolean): void {
    const canyon = new Phaser.Geom.Polygon(RAVINE.flat());
    const inside = pts.map((p) => Phaser.Geom.Polygon.Contains(canyon, p.x, p.y));
    const from = Math.max(0, inside.indexOf(true) - 2);
    const to = Math.min(pts.length - 1, inside.lastIndexOf(true) + 2);
    const over = inside.includes(true) ? pts.slice(from, to + 1) : [];
    if (over.length < 2) return;
    const first = over[0];
    const last = over[over.length - 1];
    const dx = last.x - first.x;
    const dy = last.y - first.y;
    const len = Math.hypot(dx, dy) || 1;
    const nx = -dy / len;
    const ny = dx / len;
    const keep = (i: number) => whole || i < over.length * 0.32 || i > over.length * 0.68;
    for (let i = 0; i < over.length; i += 2) {
      if (!keep(i)) continue;
      const p = over[i];
      const sag = whole ? 0 : (i < over.length / 2 ? i : over.length - i) * 0.5; // broken halves droop
      g.lineStyle(9, INK).lineBetween(p.x + nx * 12, p.y + ny * 12 + sag, p.x - nx * 12, p.y - ny * 12 + sag);
      g.lineStyle(6, 0xc08552).lineBetween(p.x + nx * 11, p.y + ny * 11 + sag, p.x - nx * 11, p.y - ny * 11 + sag);
    }
    for (const side of [12, -12]) {
      g.lineStyle(2.5, INK);
      g.beginPath();
      let open = false;
      over.forEach((p, i) => {
        if (!keep(i)) {
          open = false;
          return;
        }
        const sag = whole ? 0 : (i < over.length / 2 ? i : over.length - i) * 0.5;
        const x = p.x + nx * side;
        const y = p.y + ny * side + sag - 2;
        if (!open) g.moveTo(x, y);
        else g.lineTo(x, y);
        open = true;
      });
      g.strokePath();
    }
    for (const p of [first, last]) {
      for (const side of [14, -14]) {
        g.fillStyle(INK).fillRoundedRect(p.x + nx * side - 4, p.y + ny * side - 14, 8, 18, 2);
        g.fillStyle(0x8b5e34).fillRoundedRect(p.x + nx * side - 2.5, p.y + ny * side - 12.5, 5, 15, 1.5);
      }
    }
  }

  private sign(g: Phaser.GameObjects.Graphics, p: Point, _label: string): void {
    g.fillStyle(INK).fillCircle(p.x, p.y, 12).fillStyle(C.broken).fillCircle(p.x, p.y, 9.5);
    g.lineStyle(3, 0xffffff).lineBetween(p.x - 4, p.y - 4, p.x + 4, p.y + 4).lineBetween(p.x - 4, p.y + 4, p.x + 4, p.y - 4);
  }

  private barricade(g: Phaser.GameObjects.Graphics, p: Point): void {
    g.lineStyle(9, INK).lineBetween(p.x - 16, p.y - 12, p.x + 16, p.y + 12).lineBetween(p.x - 16, p.y + 12, p.x + 16, p.y - 12);
    g.lineStyle(5, C.trunk).lineBetween(p.x - 16, p.y - 12, p.x + 16, p.y + 12).lineBetween(p.x - 16, p.y + 12, p.x + 16, p.y - 12);
  }

  private padlock(g: Phaser.GameObjects.Graphics, p: Point): void {
    g.lineStyle(4, INK).beginPath().arc(p.x, p.y - 4, 7, Math.PI, 0).strokePath();
    g.fillStyle(INK).fillRoundedRect(p.x - 11, p.y - 5, 22, 17, 4);
    g.fillStyle(0xffd43b).fillRoundedRect(p.x - 8.5, p.y - 2.5, 17, 12, 3);
    g.fillStyle(INK).fillCircle(p.x, p.y + 3, 2.2);
  }

  private drawSites(state: StateView): void {
    const g = this.siteLayer.clear();
    const loc = new Map(state.locations.map((l) => [l.id, l]));
    const at = (id: string) => loc.get(id)!;
    const box = (x: number, y: number, w: number, h: number, fill: number, r = 3) =>
      g.fillStyle(fill).fillRoundedRect(x, y, w, h, r).lineStyle(3, INK).strokeRoundedRect(x, y, w, h, r);

    const h = at("harbour"); // a fisher's hut and a pier out to the boat
    const pier = [{ x: h.x + 34, y: h.y + 6 }, { x: h.x + 56, y: h.y + 6 }, { x: h.x + 88, y: h.y + 78 }, { x: h.x + 66, y: h.y + 78 }];
    for (const [px, py] of [[44, 30], [60, 62], [78, 62]]) box(h.x + px, h.y + py, 6, 20, 0x8b5e34, 2);
    g.fillStyle(0xc08552).fillPoints(pier, true).lineStyle(3, INK).strokePoints(pier, true);
    for (let k = 1; k < 6; k++) {
      const f = k / 6;
      g.lineStyle(1.5, 0x8b5e34).lineBetween(h.x + 34 + 32 * f, h.y + 6 + 72 * f, h.x + 56 + 32 * f, h.y + 6 + 72 * f);
    }
    // salvaged crates and a barrel on the beach
    g.fillStyle(0x000000, 0.18).fillEllipse(h.x - 96, h.y + 40, 58, 10);
    box(h.x - 120, h.y + 16, 24, 22, 0xc08552, 3);
    g.lineStyle(2, 0x8b5e34).lineBetween(h.x - 118, h.y + 18, h.x - 98, h.y + 36).lineBetween(h.x - 98, h.y + 18, h.x - 118, h.y + 36);
    box(h.x - 112, h.y - 2, 18, 18, 0xd9a066, 3);
    g.fillStyle(INK).fillEllipse(h.x - 82, h.y + 26, 22, 28).fillStyle(0x9c6644).fillEllipse(h.x - 82, h.y + 26, 17, 23);
    g.lineStyle(2, INK).lineBetween(h.x - 91, h.y + 20, h.x - 73, h.y + 20).lineBetween(h.x - 91, h.y + 32, h.x - 73, h.y + 32);

    const lh = at("lighthouse"); // tall red-and-white tower on its rock
    const lit = state.lighthouse.activated;
    const tower = [{ x: lh.x - 20, y: lh.y + 36 }, { x: lh.x + 20, y: lh.y + 36 }, { x: lh.x + 12, y: lh.y - 40 }, { x: lh.x - 12, y: lh.y - 40 }];
    g.fillStyle(0xffffff).fillPoints(tower, true);
    for (const [y0, y1] of [[24, 10], [-4, -18], [-30, -40]]) {
      const wAt = (y: number) => 20 - ((36 - y) / 76) * 8;
      g.fillStyle(0xe03131).fillPoints([{ x: lh.x - wAt(y0), y: lh.y + y0 }, { x: lh.x + wAt(y0), y: lh.y + y0 },
        { x: lh.x + wAt(y1), y: lh.y + y1 }, { x: lh.x - wAt(y1), y: lh.y + y1 }], true);
    }
    g.fillStyle(0xffffff, 0.35).fillRect(lh.x - 9, lh.y - 38, 4, 72);
    g.lineStyle(3, INK).strokePoints(tower, true);
    box(lh.x - 6, lh.y + 20, 12, 16, 0x6b4f3a, 5);
    box(lh.x - 18, lh.y - 46, 36, 7, 0x495057, 2); // gallery
    box(lh.x - 12, lh.y - 66, 24, 20, lit ? 0xffe066 : 0x9fb4ff, 3); // lamp room
    if (!lit) g.lineStyle(2, INK, 0.5).lineBetween(lh.x, lh.y - 66, lh.x, lh.y - 46);
    g.fillStyle(0xe03131).fillTriangle(lh.x - 16, lh.y - 66, lh.x + 16, lh.y - 66, lh.x, lh.y - 84);
    g.lineStyle(3, INK).strokeTriangle(lh.x - 16, lh.y - 66, lh.x + 16, lh.y - 66, lh.x, lh.y - 84);
    g.fillStyle(INK).fillCircle(lh.x, lh.y - 86, 4).fillStyle(0xffd43b).fillCircle(lh.x, lh.y - 86, 2.5);
    if (state.lighthouse.crystal_installed) {
      g.fillStyle(C.crystal).fillCircle(lh.x, lh.y - 56, 6).lineStyle(2, INK).strokeCircle(lh.x, lh.y - 56, 6);
    }

    const t = at("temple"); // stepped stone temple with a shrine on top
    g.fillStyle(0x000000, 0.18).fillEllipse(t.x + 6, t.y + 26, 140, 18);
    box(t.x - 62, t.y + 6, 124, 18, 0xcbb894, 3);
    box(t.x - 48, t.y - 10, 96, 17, 0xd9c8a4, 3);
    for (let k = 0; k < 4; k++) g.lineStyle(2, 0x9c8462).lineBetween(t.x - 14, t.y + 10 + k * 4, t.x + 14, t.y + 10 + k * 4);
    box(t.x - 36, t.y - 42, 72, 33, 0xe8dcc2, 3);
    for (const dx of [-30, 20]) box(t.x + dx, t.y - 42, 10, 33, 0xf4ecd9, 2);
    g.fillStyle(0xe0a800).fillTriangle(t.x - 44, t.y - 42, t.x + 44, t.y - 42, t.x, t.y - 70);
    g.lineStyle(3, INK).strokeTriangle(t.x - 44, t.y - 42, t.x + 44, t.y - 42, t.x, t.y - 70);
    g.fillStyle(0xffffff, 0.35).fillTriangle(t.x - 30, t.y - 45, t.x - 2, t.y - 66, t.x - 6, t.y - 45);
    const open = state.temple_lock.gate_open;
    g.fillStyle(open ? C.gateOpen : 0x5c4033).fillRoundedRect(t.x - 13, t.y - 34, 26, 25, { tl: 13, tr: 13, bl: 0, br: 0 });
    g.lineStyle(3, INK).strokeRoundedRect(t.x - 13, t.y - 34, 26, 25, { tl: 13, tr: 13, bl: 0, br: 0 });
    if (!open) {
      g.lineStyle(2.5, 0xffd43b).strokeCircle(t.x, t.y - 22, 5); // the gear lock
      if (state.temple_lock.mechanism_repaired) g.fillStyle(0xffd43b).fillCircle(t.x, t.y - 22, 2.5);
    }

    const ch = at("chamber"); // a cave in the hillside; the water rises once the gate is open
    const level = state.flood.flooded ? 1 : state.flood.started_at !== null ? 0.65 : 0.3;
    g.fillStyle(0x000000, 0.2).fillEllipse(ch.x + 6, ch.y + 28, 128, 20);
    g.fillStyle(0x9aa3b5).fillEllipse(ch.x, ch.y + 2, 124, 74).lineStyle(3.5, INK).strokeEllipse(ch.x, ch.y + 2, 124, 74);
    g.fillStyle(0xc7cfdc).fillEllipse(ch.x - 18, ch.y - 12, 60, 28);
    g.fillStyle(0x2b2f45).fillRoundedRect(ch.x - 30, ch.y - 20, 60, 46, { tl: 30, tr: 30, bl: 6, br: 6 });
    g.lineStyle(3, INK).strokeRoundedRect(ch.x - 30, ch.y - 20, 60, 46, { tl: 30, tr: 30, bl: 6, br: 6 });
    const waterTop = ch.y + 26 - level * 40;
    g.fillStyle(C.flooded, 0.9).fillRect(ch.x - 28, waterTop, 56, ch.y + 25 - waterTop);
    g.lineStyle(2, 0xbfe7ff).lineBetween(ch.x - 22, waterTop + 3, ch.x + 22, waterTop + 3);

    const crystal = state.objects.find((o) => o.id === "sun_crystal");
    const place = crystal?.location_id ? loc.get(crystal.location_id) : undefined;
    const showCrystal = !!place && !state.lighthouse.crystal_installed;
    const cy = place ? (place.id === "chamber" ? place.y + 4 : place.y - 6) : 0;
    this.looseCrystal.setVisible(showCrystal);
    this.crystalMark.setVisible(showCrystal);
    if (place) {
      this.looseCrystal.setPosition(place.x, cy);
      this.crystalMark.setPosition(place.x, cy);
    }

    // The goal, spelled out on the map: where the crystal must go, then what to do there.
    const lhLoc = at("lighthouse");
    const goal = state.lighthouse.activated ? null
      : state.lighthouse.crystal_installed ? "Light the beacon!" : "Bring the Sun Crystal here";
    this.goalBanner.setVisible(!!goal).setPosition(lhLoc.x + 140, lhLoc.y - 24);
    if (goal) this.setPill(this.goalBanner, goal, 0xfff3bf);

    for (const l of state.locations) {
      const name = `label-${l.id}`;
      if (this.children.getByName(name)) continue;
      const [ox, oy] = LABEL_OFFSET[l.id] ?? [0, -66];
      const pill = this.add.container(l.x + ox, l.y + oy).setName(name).setDepth(8);
      this.setPill(pill, l.name, 0xffffff);
    }
  }

  /** A rounded ink-outlined label with a small drop shadow; rebuilt in place when its text changes. */
  private setPill(c: Phaser.GameObjects.Container, label: string, fill: number, star = fill !== 0xffffff): void {
    if (c.getData("label") === label) return;
    c.setData("label", label);
    c.removeAll(true);
    const text = this.add.text(star ? 9 : 0, 0, label, { fontFamily: FONT, resolution: RES, fontSize: "15px", color: "#1d2142", fontStyle: "bold" })
      .setOrigin(0.5);
    const w = text.width + (star ? 40 : 20);
    const bg = this.add.graphics();
    bg.fillStyle(INK).fillRoundedRect(-w / 2, -11, w, 27, 13.5);
    bg.fillStyle(fill).fillRoundedRect(-w / 2, -14, w, 27, 13.5).lineStyle(3, INK).strokeRoundedRect(-w / 2, -14, w, 27, 13.5);
    c.add([bg, text]);
    if (star) c.add(this.add.star(-w / 2 + 16, -0.5, 5, 4, 8.5, C.crystal).setStrokeStyle(2, INK));
  }

  // --- characters ---------------------------------------------------------------------------------------------

  private makeToon(c: CharacterView): Toon {
    const shirt = hex(c.color);
    const shadow = this.add.ellipse(0, 2, 30 * TOON, 9 * TOON, 0x000000, 0.25);
    const ring = this.add.ellipse(0, 2, 44 * TOON, 16 * TOON).setStrokeStyle(4, 0xffd43b);
    const focus = this.add.ellipse(0, 2, 54 * TOON, 20 * TOON).setStrokeStyle(3, 0xffffff);
    const legs = this.add.graphics();
    const body = this.add.graphics();
    const arms = this.add.graphics();
    const face = this.add.graphics();

    // Body (shirt) and head.
    body.fillStyle(INK).fillRoundedRect(-11, -25, 22, 18, 7).fillStyle(shirt).fillRoundedRect(-9, -23, 18, 14, 5);
    if (c.id === "meera") body.fillStyle(INK).fillCircle(0, -36, 17).fillStyle(0x2f9e44).fillCircle(0, -36, 15); // hood
    body.fillStyle(INK).fillCircle(0, -36, 14.5).fillStyle(C.skin).fillCircle(0, -36, 12.5);
    if (c.id === "aria") {
      body.fillStyle(INK).fillCircle(13, -44, 7.5).fillStyle(0x7f4f24).fillCircle(13, -44, 6); // ponytail
      body.fillStyle(0x7f4f24).slice(0, -38, 12.5, Math.PI, 0, false).fillPath(); // hair
      body.fillStyle(0xff922b).fillRect(-12, -42, 24, 4); // headband
      body.lineStyle(2, INK).strokeRect(-12, -42, 24, 4);
    } else if (c.id === "kabir") {
      body.fillStyle(INK).slice(0, -40, 15, Math.PI, 0, false).fillPath();
      body.fillStyle(0xffd43b).slice(0, -40, 13, Math.PI, 0, false).fillPath(); // hard hat
      body.fillStyle(INK).fillRoundedRect(-17, -42, 34, 6, 3).fillStyle(0xffd43b).fillRoundedRect(-15, -41, 30, 4, 2);
    } else {
      body.fillStyle(0x2f9e44).slice(0, -38, 13, Math.PI, 0, false).fillPath(); // hood front
    }

    const art = this.add.container(0, 0, [legs, body, arms, face]).setScale(TOON);
    const crystal = this.add.star(15, -16, 5, 4, 8, C.crystal).setStrokeStyle(2, INK).setVisible(false);
    art.add(crystal);

    const name = this.add.text(0, 14, c.name, {
      fontFamily: FONT, resolution: RES, fontSize: "13px", color: "#1d2142", fontStyle: "bold",
      backgroundColor: c.autonomous ? "#ffffff" : "#ffd43b", padding: { x: 6, y: 1 },
    }).setOrigin(0.5, 0);
    const extras: Phaser.GameObjects.GameObject[] = [];
    let you: Phaser.GameObjects.Container | null = null;
    if (!c.autonomous) {
      // A bouncing "YOU" arrow, so a new player finds their character at once.
      const arrow = this.add.graphics();
      arrow.fillStyle(INK).fillRoundedRect(-22, -15, 44, 22, 11).fillTriangle(-9, 5, 9, 5, 0, 17);
      arrow.fillStyle(0xffd43b).fillRoundedRect(-20, -13, 40, 18, 9).fillTriangle(-6, 4, 6, 4, 0, 13);
      const label = this.add.text(0, -4, "YOU", { fontFamily: FONT, resolution: RES, fontSize: "13px", color: "#1d2142", fontStyle: "bold" })
        .setOrigin(0.5);
      you = this.add.container(0, -112, [arrow, label]);
      this.tweens.add({ targets: you, y: -120, yoyo: true, repeat: -1, duration: 520, ease: "Sine.inOut" });
      extras.push(you);
    }
    const emojiBg = this.add.graphics();
    emojiBg.fillStyle(INK).fillCircle(0, 0, 14).fillStyle(0xffffff).fillCircle(0, 0, 12);
    emojiBg.fillStyle(0xffffff).fillCircle(-12, 14, 3).fillCircle(-17, 20, 2);
    const emojiText = this.add.text(0, 0, "", { fontSize: "17px", resolution: RES }).setOrigin(0.5);
    const emoji = this.add.container(24, -104, [emojiBg, emojiText]).setVisible(false);
    this.tweens.add({ targets: emoji, y: -109, yoyo: true, repeat: -1, duration: 700, ease: "Sine.inOut" });

    const root = this.add.container(500, 350, [shadow, ring, focus, art, name, emoji, ...extras]).setDepth(10);
    root.setSize(64, 96).setInteractive({ useHandCursor: true, hitArea: new Phaser.Geom.Rectangle(-32, -86, 64, 96),
      hitAreaCallback: Phaser.Geom.Rectangle.Contains }).on("pointerdown", () => this.onSelect(c.id));
    this.tweens.add({ targets: ring, scaleX: 1.12, scaleY: 1.12, alpha: 0.6, yoyo: true, repeat: -1, duration: 700 });

    const toon: Toon = {
      root, art, legs, arms, face, ring, focus, emoji, emojiText, crystal, you, id: c.id, phase: 0, lastX: 500, lastY: 350,
      moving: false, mood: "happy", surprisedUntil: 0, nextBlink: this.time.now + 1500 + Math.random() * 2000, bubble: null,
    };
    this.drawFace(toon, false);
    return toon;
  }

  private drawLimbs(t: Toon): void {
    const swing = t.moving ? Math.sin(t.phase) : 0;
    const lift = (s: number) => (t.moving ? Math.max(0, s) * 3 : 0);
    const g = t.legs.clear();
    for (const [hip, dir] of [[-4, 1], [4, -1]] as const) {
      const fx = hip + swing * 7 * dir;
      const fy = -lift(swing * dir);
      g.lineStyle(6, INK).lineBetween(hip, -9, fx, fy);
      g.lineStyle(4, C.pants).lineBetween(hip, -9, fx, fy);
      g.fillStyle(INK).fillEllipse(fx + 1, fy, 9, 5);
    }
    const a = t.arms.clear();
    for (const [sx, dir] of [[-9, -1], [9, 1]] as const) {
      const hx = sx + dir * 3 - swing * 5 * dir;
      const hy = t.moving ? -11 : -10;
      a.lineStyle(5, INK).lineBetween(sx, -20, hx, hy);
      a.lineStyle(3, C.skin).lineBetween(sx, -20, hx, hy);
      a.fillStyle(INK).fillCircle(hx, hy, 3.2).fillStyle(C.skin).fillCircle(hx, hy, 2.2);
    }
  }

  private drawFace(t: Toon, blink: boolean): void {
    const g = t.face.clear();
    const mood: Mood = this.time.now < t.surprisedUntil ? "surprised" : t.mood;
    for (const ex of [-4.5, 4.5]) {
      if (blink) {
        g.lineStyle(2, INK).lineBetween(ex - 2.5, -36, ex + 2.5, -36);
      } else {
        const big = mood === "surprised" ? 1.3 : 1;
        g.fillStyle(INK).fillEllipse(ex, -36, 6 * big, 7.5 * big);
        g.fillStyle(0xffffff).fillCircle(ex + 1, -37.5, 1.2);
      }
    }
    g.fillStyle(C.cheek, 0.6).fillCircle(-8, -31, 2.5).fillCircle(8, -31, 2.5);
    if (mood === "happy") {
      g.lineStyle(2.2, INK).beginPath().arc(0, -31.5, 3.5, 0.15 * Math.PI, 0.85 * Math.PI).strokePath();
    } else if (mood === "worried") {
      g.lineStyle(2.2, INK).beginPath().arc(0, -27.5, 3, 1.2 * Math.PI, 1.8 * Math.PI).strokePath();
      g.lineStyle(2, INK).lineBetween(-7, -42, -3, -41).lineBetween(7, -42, 3, -41);
    } else {
      g.fillStyle(INK).fillEllipse(0, -30, 4, 5);
    }
    if (t.id === "kabir") {
      g.lineStyle(1.8, INK).strokeCircle(-4.5, -36, 4.5).strokeCircle(4.5, -36, 4.5).lineBetween(-0.5, -36, 0.5, -36);
    }
  }

  // --- speech bubbles & effects -----------------------------------------------------------------------------

  say(bubble: Bubble): void {
    const t = this.toons.get(bubble.characterId);
    if (!this.ready || !t) return;
    t.bubble?.destroy();
    const style = bubble.style;
    if (style === "shout") t.surprisedUntil = this.time.now + 2200;
    const text = this.add.text(0, 0, bubble.text, {
      fontFamily: FONT, resolution: RES, fontSize: "14px", color: style === "shout" ? "#c92a2a" : "#1d2142",
      fontStyle: style === "shout" ? "bold" : "normal", wordWrap: { width: 170 }, align: "center",
    }).setOrigin(0.5);
    const w = Math.max(44, text.width + 20);
    const h = text.height + 14;
    const bg = this.add.graphics();
    const fill = style === "think" ? 0xf1f3f5 : style === "yay" ? 0xfff3bf : 0xffffff;
    bg.fillStyle(INK).fillRoundedRect(-w / 2 - 2.5, -h / 2 - 2.5, w + 5, h + 5, 14);
    bg.fillStyle(fill).fillRoundedRect(-w / 2, -h / 2, w, h, 12);
    if (style === "think") {
      bg.fillStyle(INK).fillCircle(-6, h / 2 + 8, 5).fillCircle(-12, h / 2 + 17, 3.5);
      bg.fillStyle(fill).fillCircle(-6, h / 2 + 8, 3.5).fillCircle(-12, h / 2 + 17, 2);
    } else {
      bg.fillStyle(INK).fillTriangle(-9, h / 2 - 1, 7, h / 2 - 1, -6, h / 2 + 15);
      bg.fillStyle(fill).fillTriangle(-6, h / 2 - 2, 4, h / 2 - 2, -5, h / 2 + 10);
    }
    const c = this.add.container(t.root.x, t.root.y - BUBBLE_LIFT - h / 2, [bg, text]).setDepth(40).setScale(0.2);
    c.setData("height", h);
    c.setData("width", w);
    t.bubble = c;
    this.tweens.add({ targets: c, scale: 1, duration: 260, ease: "Back.out" });
    if (style === "oops") this.sweat(t);
    if (style === "yay") this.burst(t.root.x, t.root.y - 56, [0xffd43b, 0xffffff], 10);
    this.time.delayedCall(3800, () => {
      if (t.bubble !== c) return;
      this.tweens.add({ targets: c, alpha: 0, scale: 0.6, duration: 250, onComplete: () => c.destroy() });
      t.bubble = null;
    });
  }

  private sweat(t: Toon): void {
    const drop = this.add.graphics().setDepth(41);
    drop.fillStyle(INK).fillCircle(0, 0, 5).fillTriangle(-5, 0, 5, 0, 0, -10);
    drop.fillStyle(0x74c0fc).fillCircle(0, 0, 3.5).fillTriangle(-3.5, 0, 3.5, 0, 0, -7.5);
    drop.setPosition(t.root.x + 22, t.root.y - 66);
    this.tweens.add({ targets: drop, y: drop.y + 14, alpha: 0, duration: 1200, onComplete: () => drop.destroy() });
  }

  private burst(x: number, y: number, tint: number[], quantity: number): void {
    const p = this.add.particles(x, y, "star", {
      speed: { min: 80, max: 180 }, scale: { start: 0.7, end: 0 }, lifespan: 700, tint, emitting: false,
    }).setDepth(42);
    p.explode(quantity);
    this.time.delayedCall(900, () => p.destroy());
  }

  private confetti(x: number, y: number): void {
    const p = this.add.particles(x, y, "confetti", {
      speed: { min: 150, max: 380 }, angle: { min: 200, max: 340 }, gravityY: 420, lifespan: 2200,
      rotate: { start: 0, end: 540 }, tint: [0xff6b6b, 0xffd43b, 0x51cf66, 0x4dabf7, 0xcc5de8], emitting: false,
    }).setDepth(45);
    p.explode(90);
    this.time.delayedCall(2600, () => p.destroy());
  }

  pulse(location: LocationView, color: number): void {
    if (!this.ready) return;
    const ring = this.add.circle(location.x, location.y, 20).setStrokeStyle(5, color).setDepth(7);
    this.tweens.add({ targets: ring, radius: 70, alpha: 0, duration: 1100, onComplete: () => ring.destroy() });
    this.burst(location.x, location.y, [color, 0xffffff], 8);
  }

  /** Push overlapping speech bubbles apart (upwards) so every line stays readable. */
  private separateBubbles(): void {
    const bubbles = [...this.toons.values()].map((t) => t.bubble).filter((b): b is Phaser.GameObjects.Container => !!b)
      .sort((a, b) => b.y - a.y);
    for (let i = 1; i < bubbles.length; i++) {
      for (let j = 0; j < i; j++) {
        const a = bubbles[j];
        const b = bubbles[i];
        const overlapX = (a.getData("width") + b.getData("width")) / 2 + 6 - Math.abs(a.x - b.x);
        const overlapY = (a.getData("height") + b.getData("height")) / 2 + 6 - Math.abs(a.y - b.y);
        if (overlapX > 0 && overlapY > 0) b.y = a.y - (a.getData("height") + b.getData("height")) / 2 - 6;
      }
    }
  }

  // --- per-frame animation ------------------------------------------------------------------------------------

  update(time: number, delta: number): void {
    if (!this.frame) return;
    const { state, receivedAt } = this.frame;
    const sim = projectedSimTime(state, receivedAt, Date.now());
    const locations = new Map(state.locations.map((l) => [l.id, l]));
    const routes = new Map(state.routes.map((r) => [r.id, r]));

    for (const c of state.characters) {
      const t = this.toons.get(c.id);
      if (!t) continue;
      const target = characterPosition(c, state, sim, locations, routes);
      const first = t.root.x === 500 && t.root.y === 350;
      const nx = first ? target.x : Phaser.Math.Linear(t.root.x, target.x, 0.2);
      const ny = first ? target.y : Phaser.Math.Linear(t.root.y, target.y, 0.2);
      const dx = nx - t.lastX;
      t.moving = target.moving || Math.hypot(nx - t.lastX, ny - t.lastY) > 0.25;
      if (Math.abs(dx) > 0.2) t.art.setScale(dx < 0 ? -TOON : TOON, TOON); // face the way they walk
      t.root.setPosition(nx, ny);
      t.lastX = nx;
      t.lastY = ny;
      t.phase += t.moving ? delta * 0.018 : 0;
      t.art.y = t.moving ? -Math.abs(Math.sin(t.phase)) * 5 : Math.sin(time / 450 + nx) * 1.1;
      this.drawLimbs(t);
      const blink = time > t.nextBlink && time < t.nextBlink + 130;
      if (time > t.nextBlink + 130) t.nextBlink = time + 2200 + Math.random() * 2500;
      this.drawFace(t, blink);
      if (t.bubble) t.bubble.setPosition(nx, ny - BUBBLE_LIFT - (t.bubble.getData("height") as number) / 2);
      t.you?.setVisible(!t.bubble && !t.emoji.visible);
    }
    this.separateBubbles();

    // The storm wall creeps in from the east as the deadline nears, and retreats once the beacon is lit.
    const deadline = state.clock.deadline;
    if (deadline !== null) {
      const progress = Phaser.Math.Clamp(sim / deadline, 0, 1);
      const targetX = state.lighthouse.activated ? W + 260 : W + 150 - progress * 330;
      this.stormBank.x = Phaser.Math.Linear(this.stormBank.x, targetX, 0.04);
      const left = deadline - sim;
      if (left < 150 && !state.lighthouse.activated && time > this.nextBolt) {
        this.nextBolt = time + 1800 + Math.random() * 2600;
        const b = this.bolt.clear().setVisible(true);
        const bx = 60 + Math.random() * 120;
        const by = 60 + Math.random() * (H - 260);
        const zig = [[0, 0], [-14, 40], [4, 40], [-12, 86], [22, 30], [4, 30], [16, 0]].map(([x, y]) => ({ x: bx + x, y: by + y }));
        b.fillStyle(0xffe066).fillPoints(zig, true).lineStyle(2.5, INK).strokePoints(zig, true);
        this.time.delayedCall(160, () => this.bolt.setVisible(false));
      }
    } else {
      this.stormBank.x = W + 260;
    }

    // The restored beacon sweeps a beam of light over the sea.
    this.beam.clear();
    if (state.lighthouse.activated) {
      const lh = locations.get("lighthouse")!;
      const origin = { x: lh.x, y: lh.y - 29 };
      const angle = (time / 1400) % (Math.PI * 2);
      const tip = { x: origin.x + Math.cos(angle) * 900, y: origin.y + Math.sin(angle) * 900 };
      const side = controlPoint(origin, tip, 110);
      this.beam.fillStyle(0xffe066, 0.28).fillTriangle(origin.x, origin.y, tip.x, tip.y, side.x, side.y);
      this.beam.fillStyle(0xffe066, 0.45).fillCircle(origin.x, origin.y, 24 + Math.sin(time / 200) * 3);
    }

    // The storm rolls in during the last three minutes: darker sky, rain, then lightning.
    const remaining = state.clock.deadline !== null ? state.clock.deadline - sim : null;
    const stormy = remaining !== null && remaining < 180 && state.run.status === "running" && !state.lighthouse.activated;
    const darkness = stormy ? Math.min(0.42, ((180 - remaining!) / 180) * 0.42) : 0;
    this.storm.setFillStyle(INK, darkness);
    if (stormy && remaining! < 120 && !this.rain) {
      this.rain = this.add.particles(0, -20, "raindrop", {
        x: { min: 0, max: W }, speedY: { min: 600, max: 800 }, speedX: -80, lifespan: 1100, quantity: 3,
        frequency: 30, alpha: { start: 0.8, end: 0.4 },
      }).setDepth(31);
    }
    if (!stormy && this.rain) {
      this.rain.destroy();
      this.rain = null;
    }
    if (stormy && remaining! < 60 && time > this.nextLightning) {
      this.cameras.main.flash(120, 255, 255, 255);
      this.nextLightning = time + 4000 + Math.random() * 5000;
    }
  }
}

export class IslandMap {
  private game: Phaser.Game;
  private scene: IslandScene;

  constructor(parent: HTMLElement, onSelect: (id: string) => void) {
    this.scene = new IslandScene();
    this.scene.onSelect = onSelect;
    this.game = new Phaser.Game({
      type: Phaser.AUTO,
      parent,
      width: W * RES,
      height: H * RES,
      backgroundColor: "#4cc9f0",
      scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
      scene: this.scene,
      banner: false,
      audio: { noAudio: true },
    });
  }

  setFrame(frame: MapFrame): void {
    this.scene.setFrame(frame);
  }

  pulse(location: LocationView, color: string): void {
    this.scene.pulse(location, hex(color));
  }

  say(bubble: Bubble): void {
    this.scene.say(bubble);
  }

  /** Re-fit the canvas after its container changed size (e.g. full-screen map). */
  refresh(): void {
    this.game.scale.refresh();
  }

  destroy(): void {
    this.game.destroy(true);
  }
}
