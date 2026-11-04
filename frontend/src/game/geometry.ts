import type { CharacterView, LocationView, RouteView, StateView } from "../types/api";

export interface Point {
  x: number;
  y: number;
}

/** How far each route bows sideways (pixels), so parallel routes such as bridge vs. ravine climb don't overlap. */
export const ROUTE_BEND: Record<string, number> = {
  cliff_stairs: -40,
  coast_road: 30,
  main_bridge: -30,
  ravine_climb: 70,
  forest_path: -35,
  forest_trail: 40,
  temple_gate: -25,
};

export function controlPoint(a: Point, b: Point, bend: number): Point {
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  return { x: mx - (dy / len) * bend, y: my + (dx / len) * bend };
}

/** Quadratic Bézier from a to b, t in [0, 1]. */
export function pointOnCurve(a: Point, b: Point, bend: number, t: number): Point {
  const c = controlPoint(a, b, bend);
  const u = 1 - t;
  return {
    x: u * u * a.x + 2 * u * t * c.x + t * t * b.x,
    y: u * u * a.y + 2 * u * t * c.y + t * t * b.y,
  };
}

export function sampleCurve(a: Point, b: Point, bend: number, steps = 24): Point[] {
  return Array.from({ length: steps + 1 }, (_, i) => pointOnCurve(a, b, bend, i / steps));
}

export const clamp01 = (v: number) => Math.min(1, Math.max(0, v));

/**
 * Best estimate of the backend's simulated clock right now, for smooth animation only.
 * It never runs more than one tick ahead of the last authoritative value, and it stands still
 * when the run is paused or over - so the map can lag the backend but never invent progress.
 */
export function projectedSimTime(state: StateView, receivedAtMs: number, nowMs: number): number {
  const { clock, run } = state;
  if (run.status !== "running" || run.paused) return clock.now;
  const elapsed = Math.max(0, (nowMs - receivedAtMs) / 1000) * run.sim_speed;
  let t = clock.now + Math.min(elapsed, clock.tick_seconds);
  if (clock.deadline !== null) t = Math.min(t, clock.deadline);
  return t;
}

/** Small fixed offsets so characters sharing a location stand side by side. */
const SLOT_OFFSETS: Point[] = [{ x: -48, y: 34 }, { x: 0, y: 52 }, { x: 48, y: 34 }];

export function characterPosition(
  character: CharacterView,
  state: StateView,
  simNow: number,
  locations: Map<string, LocationView>,
  routes: Map<string, RouteView>,
): Point & { moving: boolean } {
  const travel = character.travel;
  if (travel) {
    const from = locations.get(travel.from_location);
    const to = locations.get(travel.to_location);
    if (from && to) {
      const span = Math.max(1, travel.arrive_at - travel.depart_at);
      const t = clamp01((simNow - travel.depart_at) / span);
      const route = routes.get(travel.route_id);
      if (route) {
        const a = locations.get(route.a)!;
        const b = locations.get(route.b)!;
        const forward = route.a === travel.from_location;
        const p = pointOnCurve(a, b, ROUTE_BEND[route.id] ?? 0, forward ? t : 1 - t);
        return { ...p, moving: true };
      }
      return { x: from.x + (to.x - from.x) * t, y: from.y + (to.y - from.y) * t, moving: true };
    }
  }
  const loc = character.location_id ? locations.get(character.location_id) : undefined;
  if (!loc) return { x: 500, y: 350, moving: false };
  const here = state.characters.filter((c) => !c.travel && c.location_id === character.location_id);
  const slot = SLOT_OFFSETS[Math.max(0, here.findIndex((c) => c.id === character.id)) % SLOT_OFFSETS.length];
  return { x: loc.x + slot.x, y: loc.y + slot.y, moving: false };
}

export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
