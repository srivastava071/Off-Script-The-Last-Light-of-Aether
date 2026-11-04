import type { CharacterView, StateView } from "../types/api";

export function character(over: Partial<CharacterView> = {}): CharacterView {
  return {
    id: "aria", name: "Aria", title: "The Explorer", color: "#f2a541", personality: "", primary_goal: "",
    abilities: ["climb"], restrictions: [], autonomous: false, location_id: "harbour", travel: null, activity: null,
    inventory: [], plan: null, trust: {}, orders: [], replans: 0, adaptations: 0, ...over,
  };
}

export function state(over: Partial<StateView> = {}): StateView {
  return {
    run: { id: "r1", mode: "game", status: "running", player_character: "aria", ai_mode: "mock", paused: false, sim_speed: 1 },
    clock: { now: 100, deadline: 600, remaining: 500, tick_seconds: 5 },
    locations: [
      { id: "harbour", name: "Abandoned Harbour", description: "", x: 190, y: 580 },
      { id: "bridge", name: "Broken Bridge", description: "", x: 470, y: 520 },
    ],
    routes: [{
      id: "coast_road", name: "Coast Road", a: "harbour", b: "bridge", base_seconds: 35, status: "open",
      obstructed: false, blocked_by: null, requires_ability: null, hazard: null, hazard_active: false,
    }],
    characters: [character()],
    objects: [],
    temple_lock: { mechanism_repaired: false, symbols_decoded: false, gate_open: false },
    lighthouse: { operational: false, crystal_installed: false, activated: false, activated_at: null },
    flood: { started_at: null, floods_at: null, flooded: false },
    story: {
      beats: [], objectives: [], assessment: { progress: 0, risk: "on_track", note: "", blocked: [] }, ending: null,
      ai: {
        deliberations_requested: 0, deliberations_applied: 0, fallbacks: 0, invalid_answers: 0, deliberations_discarded: 0,
        llm_replies: 0, template_replies: 0, calls_succeeded: 0, total_latency_ms: 0, providers: {},
      },
      chapters: [],
      twists: { used: 0, max: 3, ready_at: null, examples: [] },
    },
    last_event_seq: 0,
    available_actions: [],
    ...over,
  };
}
