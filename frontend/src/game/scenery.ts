/**
 * Paints the island's static scenery once onto a 2D canvas: gradients, soft shadows and texture
 * that Phaser's flat vector graphics can't do. Everything that moves stays a Phaser object.
 */
import type { Point } from "./geometry";

const INK = "#1d2142";

/** Deterministic pseudo-random numbers, so the island looks the same on every device. */
function rng(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function trace(ctx: CanvasRenderingContext2D, pts: Point[]): void {
  ctx.beginPath();
  ctx.moveTo(pts[0].x, pts[0].y);
  for (const p of pts.slice(1)) ctx.lineTo(p.x, p.y);
  ctx.closePath();
}

function scale(pts: Point[], cx: number, cy: number, kx: number, ky = kx, dy = 0): Point[] {
  return pts.map((p) => ({ x: cx + (p.x - cx) * kx, y: cy + (p.y - cy) * ky + dy }));
}

function sea(ctx: CanvasRenderingContext2D, w: number, h: number): void {
  const g = ctx.createLinearGradient(0, 0, 0, h);
  g.addColorStop(0, "#74daf8");
  g.addColorStop(0.55, "#45bdee");
  g.addColorStop(1, "#2a98d6");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
  // soft light bands and glints on the water
  const r = rng(7);
  ctx.save();
  ctx.globalAlpha = 0.12;
  ctx.strokeStyle = "#ffffff";
  ctx.lineCap = "round";
  for (let i = 0; i < 14; i++) {
    const y = 20 + i * 52 + r() * 18;
    ctx.lineWidth = 6 + r() * 6;
    ctx.beginPath();
    ctx.moveTo(-20, y);
    ctx.bezierCurveTo(w * 0.3, y - 18, w * 0.6, y + 18, w + 20, y - 6);
    ctx.stroke();
  }
  ctx.restore();
  ctx.fillStyle = "rgba(255,255,255,0.75)";
  for (let i = 0; i < 70; i++) {
    const x = r() * w;
    const y = r() * h;
    const s = 1 + r() * 2.2;
    ctx.beginPath();
    ctx.moveTo(x, y - s * 2);
    ctx.lineTo(x + s * 0.5, y - s * 0.5);
    ctx.lineTo(x + s * 2, y);
    ctx.lineTo(x + s * 0.5, y + s * 0.5);
    ctx.lineTo(x, y + s * 2);
    ctx.lineTo(x - s * 0.5, y + s * 0.5);
    ctx.lineTo(x - s * 2, y);
    ctx.lineTo(x - s * 0.5, y - s * 0.5);
    ctx.closePath();
    ctx.fill();
  }
}

function island(ctx: CanvasRenderingContext2D, coast: Point[], w: number, h: number): Point[] {
  const cx = w / 2;
  const cy = h / 2;
  // drop shadow under the island
  ctx.save();
  ctx.filter = "blur(10px)";
  ctx.fillStyle = "rgba(10, 60, 110, 0.38)";
  trace(ctx, scale(coast, cx, cy, 1.01, 1.01, 16));
  ctx.fill();
  ctx.restore();
  // shallow water rings
  ctx.fillStyle = "rgba(150, 236, 255, 0.55)";
  trace(ctx, scale(coast, cx, cy, 1.075, 1.09));
  ctx.fill();
  ctx.fillStyle = "rgba(205, 248, 255, 0.75)";
  trace(ctx, scale(coast, cx, cy, 1.035, 1.045));
  ctx.fill();
  ctx.save();
  ctx.setLineDash([14, 10]);
  ctx.lineWidth = 3;
  ctx.strokeStyle = "rgba(255,255,255,0.95)";
  trace(ctx, scale(coast, cx, cy, 1.05, 1.065));
  ctx.stroke();
  ctx.restore();
  // beach
  const sand = ctx.createLinearGradient(0, 80, 0, 670);
  sand.addColorStop(0, "#ffe9b3");
  sand.addColorStop(1, "#f5cc78");
  ctx.fillStyle = sand;
  trace(ctx, coast);
  ctx.fill();
  ctx.lineJoin = "round";
  ctx.lineWidth = 5;
  ctx.strokeStyle = INK;
  ctx.stroke();
  // grass
  const inner = scale(coast, cx, cy, 0.955, 0.935);
  const grass = ctx.createRadialGradient(470, 330, 40, 500, 360, 520);
  grass.addColorStop(0, "#a9e884");
  grass.addColorStop(0.7, "#86d465");
  grass.addColorStop(1, "#68be4c");
  ctx.fillStyle = grass;
  trace(ctx, inner);
  ctx.fill();
  ctx.lineWidth = 3;
  ctx.strokeStyle = "#4b9f37";
  ctx.stroke();
  return inner;
}

function grassTexture(ctx: CanvasRenderingContext2D, inner: Point[]): void {
  ctx.save();
  trace(ctx, inner);
  ctx.clip();
  const r = rng(42);
  for (let i = 0; i < 26; i++) {
    const x = 90 + r() * 840;
    const y = 110 + r() * 520;
    ctx.fillStyle = r() > 0.5 ? "rgba(255,255,255,0.10)" : "rgba(40,110,30,0.10)";
    ctx.beginPath();
    ctx.ellipse(x, y, 40 + r() * 70, 18 + r() * 30, r() * Math.PI, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.lineCap = "round";
  for (let i = 0; i < 90; i++) {
    const x = 100 + r() * 820;
    const y = 120 + r() * 500;
    ctx.strokeStyle = "rgba(60,140,45,0.75)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x - 4, y - 6);
    ctx.lineTo(x, y);
    ctx.lineTo(x + 4, y - 7);
    ctx.stroke();
    if (i % 4 === 0) {
      const petal = ["#ffffff", "#ffa8c5", "#ffe066", "#d0bfff"][i % 4 === 0 ? (i / 4) % 4 : 0];
      for (let k = 0; k < 5; k++) {
        const a = (k / 5) * Math.PI * 2;
        ctx.fillStyle = petal;
        ctx.beginPath();
        ctx.arc(x + 9 + Math.cos(a) * 2.6, y - 3 + Math.sin(a) * 2.6, 2, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.fillStyle = "#f59f00";
      ctx.beginPath();
      ctx.arc(x + 9, y - 3, 1.4, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.restore();
}

function mountain(ctx: CanvasRenderingContext2D, x: number, y: number, s: number): void {
  const left = { x: x - s, y: y + s * 0.62 };
  const right = { x: x + s, y: y + s * 0.62 };
  const top = { x, y: y - s * 0.85 };
  const shape = () => {
    ctx.beginPath();
    ctx.moveTo(left.x, left.y);
    ctx.quadraticCurveTo(x - s * 0.45, y - s * 0.2, top.x - s * 0.08, top.y + s * 0.06);
    ctx.quadraticCurveTo(top.x, top.y - s * 0.04, top.x + s * 0.08, top.y + s * 0.06);
    ctx.quadraticCurveTo(x + s * 0.45, y - s * 0.2, right.x, right.y);
    ctx.closePath();
  };
  ctx.save();
  ctx.filter = "blur(4px)";
  ctx.fillStyle = "rgba(30,60,30,0.25)";
  ctx.beginPath();
  ctx.ellipse(x + s * 0.15, y + s * 0.66, s * 1.05, s * 0.18, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
  ctx.save();
  shape();
  ctx.fillStyle = "#c7cfdc";
  ctx.fill();
  ctx.clip();
  ctx.fillStyle = "#98a3b8"; // shadow side
  ctx.beginPath();
  ctx.moveTo(top.x, top.y);
  ctx.lineTo(x + s * 0.15, y + s * 0.1);
  ctx.lineTo(x - s * 0.05, y + s * 0.7);
  ctx.lineTo(right.x + 4, right.y + 4);
  ctx.lineTo(right.x + 4, top.y);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = "#ffffff"; // wavy snowcap
  ctx.beginPath();
  ctx.moveTo(x - s * 0.5, y - s * 0.2);
  ctx.lineTo(top.x, top.y - 6);
  ctx.lineTo(x + s * 0.5, y - s * 0.2);
  ctx.quadraticCurveTo(x + s * 0.3, y - s * 0.06, x + s * 0.18, y - s * 0.24);
  ctx.quadraticCurveTo(x + s * 0.02, y - s * 0.06, x - s * 0.12, y - s * 0.24);
  ctx.quadraticCurveTo(x - s * 0.3, y - s * 0.06, x - s * 0.5, y - s * 0.2);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
  shape();
  ctx.lineWidth = 3.5;
  ctx.strokeStyle = INK;
  ctx.stroke();
}

function ravine(ctx: CanvasRenderingContext2D, pts: Point[]): void {
  // a canyon: dark depths, lit rims, and a stream far below
  ctx.save();
  ctx.filter = "blur(5px)";
  ctx.fillStyle = "rgba(40,30,10,0.35)";
  trace(ctx, pts.map((p) => ({ x: p.x + 6, y: p.y + 6 })));
  ctx.fill();
  ctx.restore();
  const g = ctx.createLinearGradient(552, 0, 650, 0);
  g.addColorStop(0, "#8b5e3c");
  g.addColorStop(0.5, "#3a2418");
  g.addColorStop(1, "#7a4f33");
  ctx.fillStyle = g;
  trace(ctx, pts);
  ctx.fill();
  ctx.save();
  trace(ctx, pts);
  ctx.clip();
  ctx.strokeStyle = "#5fc8f0";
  ctx.lineWidth = 3;
  ctx.lineCap = "round";
  const n = pts.length;
  ctx.beginPath();
  for (let i = 0; i < n / 2; i++) {
    const a = pts[i];
    const b = pts[n - 1 - i];
    const m = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    if (i === 0) ctx.moveTo(m.x, m.y);
    else ctx.lineTo(m.x, m.y);
  }
  ctx.stroke();
  ctx.restore();
  ctx.lineJoin = "round";
  ctx.lineWidth = 4;
  ctx.strokeStyle = "#b98a5e"; // lit rim
  trace(ctx, scale(pts, 605, 480, 1.04, 1.0));
  ctx.stroke();
  ctx.lineWidth = 3.5;
  ctx.strokeStyle = INK;
  trace(ctx, pts);
  ctx.stroke();
  const r = rng(3);
  for (const p of pts) {
    if (r() > 0.6) continue;
    ctx.fillStyle = "#a8957f";
    ctx.beginPath();
    ctx.ellipse(p.x + (r() - 0.5) * 16, p.y + (r() - 0.5) * 10, 6 + r() * 4, 4 + r() * 2, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = INK;
    ctx.stroke();
  }
}

function patch(ctx: CanvasRenderingContext2D, x: number, y: number, rx: number, ry: number, fill: string, edge?: string) {
  ctx.fillStyle = fill;
  ctx.beginPath();
  ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2);
  ctx.fill();
  if (edge) {
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = edge;
    ctx.stroke();
  }
}

function grounds(ctx: CanvasRenderingContext2D): void {
  patch(ctx, 450, 230, 200, 112, "rgba(46,120,40,0.28)"); // forest floor
  patch(ctx, 742, 408, 84, 30, "#e9dcc0", "#b9a47e"); // temple plaza
  ctx.save();
  ctx.setLineDash([5, 6]);
  patch(ctx, 742, 408, 66, 22, "rgba(0,0,0,0)", "rgba(150,125,90,0.7)");
  ctx.restore();
  patch(ctx, 130, 212, 62, 26, "#b7bfcc", INK); // lighthouse rock
  patch(ctx, 124, 206, 46, 16, "#d3d9e3");
  patch(ctx, 470, 545, 52, 18, "rgba(180,140,90,0.35)"); // bridgehead
}

function palm(ctx: CanvasRenderingContext2D, x: number, y: number, s: number, lean: number): void {
  ctx.save();
  ctx.translate(x, y);
  ctx.fillStyle = "rgba(0,0,0,0.18)";
  ctx.beginPath();
  ctx.ellipse(lean * 18 * s, 4, 26 * s, 7 * s, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.lineCap = "round";
  ctx.strokeStyle = INK;
  ctx.lineWidth = 11 * s;
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.quadraticCurveTo(lean * 8 * s, -30 * s, lean * 18 * s, -58 * s);
  ctx.stroke();
  ctx.strokeStyle = "#b07a4a";
  ctx.lineWidth = 7 * s;
  ctx.stroke();
  const tx = lean * 18 * s;
  const ty = -58 * s;
  for (let k = 0; k < 6; k++) {
    const a = -Math.PI / 2 + (k - 2.5) * 0.62;
    const ex = tx + Math.cos(a) * 34 * s;
    const ey = ty + Math.sin(a) * 22 * s + 10 * s;
    ctx.beginPath();
    ctx.moveTo(tx, ty);
    ctx.quadraticCurveTo((tx + ex) / 2, ty - 14 * s, ex, ey);
    ctx.quadraticCurveTo((tx + ex) / 2, ty - 2 * s, tx, ty);
    ctx.fillStyle = k % 2 ? "#3fae49" : "#56c45c";
    ctx.fill();
    ctx.lineWidth = 2.2;
    ctx.strokeStyle = INK;
    ctx.stroke();
  }
  ctx.fillStyle = "#7a4a2a";
  for (const [dx, dy] of [[-4, 4], [4, 5], [0, 8]]) {
    ctx.beginPath();
    ctx.arc(tx + dx * s, ty + dy * s, 4 * s, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function beachBits(ctx: CanvasRenderingContext2D): void {
  // starfish and shells along the sand
  const star = (x: number, y: number, r: number, color: string) => {
    ctx.beginPath();
    for (let i = 0; i < 10; i++) {
      const a = -Math.PI / 2 + (i / 10) * Math.PI * 2;
      const rr = i % 2 ? r * 0.45 : r;
      ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr);
    }
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
    ctx.lineWidth = 1.8;
    ctx.strokeStyle = INK;
    ctx.stroke();
  };
  star(398, 640, 8, "#ff8787");
  star(905, 470, 7, "#ffa94d");
  star(118, 470, 6, "#ff8787");
  for (const [x, y] of [[700, 640], [320, 652], [940, 250]]) {
    ctx.fillStyle = "#fff0f6";
    ctx.beginPath();
    ctx.arc(x, y, 6, Math.PI, 0);
    ctx.closePath();
    ctx.fill();
    ctx.lineWidth = 1.8;
    ctx.strokeStyle = INK;
    ctx.stroke();
  }
}

export function paintScenery(ctx: CanvasRenderingContext2D, w: number, h: number, coast: Point[], ravinePts: Point[]): void {
  sea(ctx, w, h);
  const inner = island(ctx, coast, w, h);
  grassTexture(ctx, inner);
  grounds(ctx);
  ravine(ctx, ravinePts);
  for (const [x, y, s] of [[700, 258, 34], [905, 362, 34], [835, 300, 42], [790, 278, 52]] as const) mountain(ctx, x, y, s);
  palm(ctx, 92, 560, 0.9, -1);
  palm(ctx, 300, 625, 0.8, 1);
  palm(ctx, 905, 560, 0.85, 1);
  beachBits(ctx);
}
