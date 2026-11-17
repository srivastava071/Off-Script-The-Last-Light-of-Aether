// Mirrors backend/app/schemas/views.py. The backend is the source of truth for all of these.

export type GameMode = "default" | "game";
export type RunStatus = "created" | "running" | "finished" | "abandoned";
export type CharacterId = "aria" | "kabir" | "meera";
export type EndingId = "light_returns" | "costly_victory" | "unexpected_route" | "last_storm";

export interface Health {
  status: string;
  version: string;
  ai_provider: string;
  ai_mode: "mock" | "live";
  llm_model: string | null;
  llm_providers: string[];
  sim_tick_seconds: number;
  game_deadline_seconds: number;
}

export interface ProposedAction {
  actor: string;
  type: string;
  destination?: string | null;
  route_id?: string | null;
  object_id?: string | null;
  target_id?: string | null;
  seconds?: number | null;
  message?: string | null;
  topic?: "plan" | "news" | null;
  request?: string | null;
}

export interface ActionOption {
  action: ProposedAction;
  label: string;
  seconds: number;
  available: boolean;
  reason: string | null;
}

export interface WorldEvent {
  seq: number;
  time: number;
  kind: string;
  description: string;
  actor: string | null;
  location_id: string | null;
  data: Record<string, unknown>;
}

export interface ActionResult {
  ok: boolean;
  message: string;
  events: WorldEvent[];
  completes_at: number | null;
  duplicate: boolean;
}

export interface LocationView {
  id: string;
  name: string;
  description: string;
  x: number;
  y: number;
}

export interface RouteView {
  id: string;
  name: string;
  a: string;
  b: string;
  base_seconds: number;
  status: "open" | "broken" | "locked" | "flooded";
  obstructed: boolean;
  blocked_by: string | null;
  requires_ability: string | null;
  hazard: string | null;
  hazard_active: boolean;
}

export interface TravelView {
  route_id: string;
  from_location: string;
  to_location: string;
  depart_at: number;
  arrive_at: number;
  progress: number;
}

export interface ActivityView {
  type: string;
  label: string;
  started_at: number;
  completes_at: number;
}

export interface PlanView {
  goal: string;
  summary: string;
  strategy: string;
  status: string;
}

export interface CharacterView {
  id: CharacterId;
  name: string;
  title: string;
  color: string;
  personality: string;
  primary_goal: string;
  abilities: string[];
  restrictions: string[];
  autonomous: boolean;
  location_id: string | null;
  travel: TravelView | null;
  activity: ActivityView | null;
  inventory: string[];
  plan: PlanView | null;
  trust: Record<string, number>;
  orders: string[]; // player instructions still to carry out
  replans: number;
  adaptations: number;
  mind: MindView;
}

/** Mind View: one thing a character believes, next to what is actually true. */
export interface BeliefFact {
  kind: "route" | "item" | "teammate" | "temple" | "lighthouse" | "flood";
  subject: string;
  believed: string;
  actual: string;
  up_to_date: boolean;
  as_of: number | null;
  route_id: string | null;
  believed_location: string | null;
  actual_location: string | null;
}

export interface MindMemory {
  time: number;
  text: string;
  source: string; // saw | did | told | signal | briefing
  from_id: string | null;
  importance: number;
}

export interface Thinking {
  since: number;
  chosen: string;
  chosen_by: "rules" | "ai" | "lesson" | "player";
  trigger: string | null;
  thought: string | null;
  options: { strategy: string; summary: string; chosen: boolean }[];
}

export interface MindView {
  thinking: Thinking | null;
  beliefs: BeliefFact[];
  outdated: number;
  memories: MindMemory[];
  lessons: { id: number; text: string; status: "kept" | "trying"; used: boolean }[];
}

/** Gameplay graphs for one run, built from its recorded events. */
export interface RunAnalytics {
  duration: number;
  deadline: number | null;
  beats_total: number;
  progress: { time: number; title: string; reached: number }[];
  timelines: {
    id: CharacterId; name: string; color: string;
    segments: { start: number; end: number; kind: "travel" | "work"; label: string }[];
    travel: number; work: number; waiting: number;
  }[];
  decisions: {
    id: CharacterId; name: string; color: string;
    plan_changes: number; adaptations: number; ai_choices: number; lessons_used: number; failed_actions: number;
  }[];
}

export interface RunSummary {
  id: string;
  mode: GameMode;
  player_character: string | null;
  status: RunStatus;
  ending: EndingId | null;
  sim_time: number;
  created_at: string;
  updated_at: string;
}

/** Team journal: lessons carried from one game to the next. */
export interface Lesson {
  id: number;
  character_id: CharacterId;
  character: string;
  text: string;
  evidence: string;
  status: "trying" | "kept" | "rejected";
  result: string | null;
  learned_in_run: string;
  tested_in_run: string | null;
  baseline_seconds: number;
  tested_seconds: number | null;
  created_at: string;
}

export interface JournalRun {
  run_id: string;
  mode: GameMode;
  player_character: string | null;
  ending: EndingId;
  ending_title: string;
  finished_at: number;
  lessons_used: number[];
  note: string;
  created_at: string;
}

export interface Journal {
  lessons: Lesson[];
  runs: JournalRun[];
}

export interface ObjectView {
  id: string;
  name: string;
  kind: string;
  location_id: string | null;
  carried_by: string | null;
}

export interface StoryBeat {
  id: string;
  title: string;
  reached_at: number | null;
}

export interface Objective {
  id: string;
  title: string;
  description: string;
  optional: boolean;
  status: "pending" | "complete" | "failed";
  resolved_at: number | null;
}

export interface Assessment {
  progress: number;
  risk: "on_track" | "at_risk" | "failing";
  note: string;
  blocked: string[];
}

export interface EndingResult {
  ending: EndingId;
  title: string;
  main_success: boolean;
  finished_at: number;
  explanation: string;
  summary: string;
  objectives: Objective[];
  routes: Record<string, string[]>;
  adaptations: string[];
  key_events: string[];
  stats: Record<string, number>;
  narration: string | null;
  narrated_by: string | null;
}

export interface AIStats {
  deliberations_requested: number;
  deliberations_applied: number;
  fallbacks: number;
  invalid_answers: number;
  deliberations_discarded: number;
  llm_replies: number;
  template_replies: number;
  calls_succeeded: number;
  total_latency_ms: number;
  providers: Record<string, number>;
}

/** One page of the live storybook (template prose, or rewritten by an AI narrator). */
export interface Chapter {
  id: number;
  time: number;
  title: string;
  text: string;
  kind: "beat" | "twist" | string;
  generated_by: string;
}

export interface TwistsInfo {
  used: number;
  max: number;
  ready_at: number | null;
  examples: string[];
}

export interface StateView {
  run: {
    id: string;
    mode: GameMode;
    status: RunStatus;
    player_character: CharacterId | null;
    ai_mode: "mock" | "live";
    paused: boolean;
    sim_speed: number;
  };
  clock: { now: number; deadline: number | null; remaining: number | null; tick_seconds: number };
  locations: LocationView[];
  routes: RouteView[];
  characters: CharacterView[];
  objects: ObjectView[];
  temple_lock: { mechanism_repaired: boolean; symbols_decoded: boolean; gate_open: boolean };
  lighthouse: { operational: boolean; crystal_installed: boolean; activated: boolean; activated_at: number | null };
  flood: { started_at: number | null; floods_at: number | null; flooded: boolean };
  story: {
    beats: StoryBeat[];
    objectives: Objective[];
    assessment: Assessment;
    ending: EndingResult | null;
    ai: AIStats;
    chapters: Chapter[];
    twists: TwistsInfo;
  };
  last_event_seq: number;
  available_actions: ActionOption[];
}

export interface CreatedRun {
  run_id: string;
  token: string;
  state: StateView;
}

export interface EventsView {
  events: WorldEvent[];
  last_event_seq: number;
}
