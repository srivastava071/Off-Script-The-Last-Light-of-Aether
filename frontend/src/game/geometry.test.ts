import { character, state } from "../test/fixtures";
import { characterPosition, formatClock, pointOnCurve, projectedSimTime } from "./geometry";

const locs = (s = state()) => new Map(s.locations.map((l) => [l.id, l]));
const routes = (s = state()) => new Map(s.routes.map((r) => [r.id, r]));

describe("projectedSimTime", () => {
  it("never runs more than one tick ahead of the server clock", () => {
    const s = state();
    expect(projectedSimTime(s, 0, 2_000)).toBe(102);
    expect(projectedSimTime(s, 0, 60_000)).toBe(105); // capped at now + tick_seconds
  });

  it("stands still when paused or finished", () => {
    const paused = state({ run: { ...state().run, paused: true } });
    const done = state({ run: { ...state().run, status: "finished" } });
    expect(projectedSimTime(paused, 0, 10_000)).toBe(100);
    expect(projectedSimTime(done, 0, 10_000)).toBe(100);
  });

  it("never passes the deadline", () => {
    const s = state({ clock: { now: 598, deadline: 600, remaining: 2, tick_seconds: 5 } });
    expect(projectedSimTime(s, 0, 60_000)).toBe(600);
  });
});

describe("characterPosition", () => {
  it("stands at the location when idle", () => {
    const s = state();
    const p = characterPosition(s.characters[0], s, 100, locs(s), routes(s));
    expect(p.moving).toBe(false);
    expect(Math.abs(p.x - 190)).toBeLessThanOrEqual(48); // side-by-side slots are 48px apart
  });

  it("moves along the route according to the server's travel times", () => {
    const traveller = character({
      location_id: null,
      travel: { route_id: "coast_road", from_location: "harbour", to_location: "bridge", depart_at: 100, arrive_at: 128, progress: 0 },
    });
    const s = state({ characters: [traveller] });
    const start = characterPosition(traveller, s, 100, locs(s), routes(s));
    const end = characterPosition(traveller, s, 128, locs(s), routes(s));
    const past = characterPosition(traveller, s, 500, locs(s), routes(s));
    expect(start).toMatchObject({ x: 190, y: 580, moving: true });
    expect(end.x).toBeCloseTo(470);
    expect(past.x).toBeCloseTo(470); // never overshoots the destination
  });

  it("travels the route backwards when going from b to a", () => {
    const traveller = character({
      location_id: null,
      travel: { route_id: "coast_road", from_location: "bridge", to_location: "harbour", depart_at: 0, arrive_at: 10, progress: 0 },
    });
    const s = state({ characters: [traveller] });
    expect(characterPosition(traveller, s, 0, locs(s), routes(s)).x).toBeCloseTo(470);
  });
});

describe("helpers", () => {
  it("curves pass through both ends", () => {
    const a = { x: 0, y: 0 };
    const b = { x: 100, y: 0 };
    expect(pointOnCurve(a, b, 40, 0)).toEqual(a);
    expect(pointOnCurve(a, b, 40, 1)).toEqual(b);
    expect(pointOnCurve(a, b, 40, 0.5).y).not.toBe(0);
  });

  it("formats clocks", () => {
    expect(formatClock(0)).toBe("0:00");
    expect(formatClock(605)).toBe("10:05");
    expect(formatClock(-3)).toBe("0:00");
  });
});
