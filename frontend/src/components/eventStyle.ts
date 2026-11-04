import {
  Anchor, BookOpen, Brain, CloudLightning, Compass, Construction, DoorOpen, Droplets, Flag, Footprints, Gem,
  Hammer, Handshake, Lightbulb, type LucideIcon, Megaphone, MessageCircle, Radio, Search, ShieldAlert, Sparkles,
  Target, TriangleAlert, Wand2, Wrench, X, CircleCheck, CircleX,
} from "lucide-react";

import type { WorldEvent } from "../types/api";

export type Tone = "muted" | "amber" | "teal" | "danger" | "ok" | "sky";
export type EventGroup = "story" | "adapt" | "talk" | "action" | "move";

interface Style {
  icon: LucideIcon;
  tone: Tone;
  group: EventGroup;
}

const STYLES: Record<string, Style> = {
  travel_started: { icon: Footprints, tone: "muted", group: "move" },
  arrived: { icon: Anchor, tone: "muted", group: "move" },
  trap_sprung: { icon: TriangleAlert, tone: "danger", group: "action" },
  item_picked_up: { icon: Gem, tone: "muted", group: "action" },
  item_dropped: { icon: Gem, tone: "muted", group: "action" },
  item_given: { icon: Handshake, tone: "teal", group: "action" },
  inspected: { icon: Search, tone: "muted", group: "action" },
  searched: { icon: Search, tone: "muted", group: "action" },
  talked: { icon: MessageCircle, tone: "sky", group: "talk" },
  asked: { icon: MessageCircle, tone: "sky", group: "talk" },
  help_requested: { icon: Handshake, tone: "sky", group: "talk" },
  help_accepted: { icon: Handshake, tone: "ok", group: "talk" },
  help_declined: { icon: X, tone: "danger", group: "talk" },
  signalled: { icon: Megaphone, tone: "teal", group: "talk" },
  plan_changed: { icon: Lightbulb, tone: "muted", group: "adapt" },
  llm_deliberation: { icon: Brain, tone: "teal", group: "adapt" },
  action_started: { icon: Wrench, tone: "muted", group: "action" },
  action_failed: { icon: ShieldAlert, tone: "danger", group: "action" },
  route_discovered: { icon: Compass, tone: "amber", group: "story" },
  traps_marked: { icon: Flag, tone: "ok", group: "action" },
  bridge_repaired: { icon: Hammer, tone: "ok", group: "story" },
  route_blocked: { icon: Construction, tone: "danger", group: "story" },
  route_cleared: { icon: Construction, tone: "ok", group: "story" },
  mechanism_repaired: { icon: Wrench, tone: "ok", group: "story" },
  symbols_decoded: { icon: BookOpen, tone: "ok", group: "story" },
  gate_opened: { icon: DoorOpen, tone: "teal", group: "story" },
  flood_warning: { icon: Droplets, tone: "danger", group: "story" },
  chamber_flooded: { icon: Droplets, tone: "danger", group: "story" },
  lighthouse_repaired: { icon: Wrench, tone: "ok", group: "story" },
  crystal_installed: { icon: Gem, tone: "amber", group: "story" },
  lighthouse_activated: { icon: Sparkles, tone: "amber", group: "story" },
  run_started: { icon: Flag, tone: "amber", group: "story" },
  run_ended: { icon: Flag, tone: "amber", group: "story" },
  story_beat: { icon: BookOpen, tone: "amber", group: "story" },
  objective_updated: { icon: Target, tone: "amber", group: "story" },
  director_note: { icon: Compass, tone: "amber", group: "story" },
  storm_warning: { icon: CloudLightning, tone: "danger", group: "story" },
  command_given: { icon: Radio, tone: "sky", group: "talk" },
  order_accepted: { icon: CircleCheck, tone: "ok", group: "talk" },
  order_refused: { icon: CircleX, tone: "danger", group: "talk" },
  order_failed: { icon: ShieldAlert, tone: "danger", group: "talk" },
  order_completed: { icon: CircleCheck, tone: "teal", group: "talk" },
  radio_message: { icon: Radio, tone: "sky", group: "talk" },
  story_twist: { icon: Wand2, tone: "amber", group: "story" },
};

const FALLBACK: Style = { icon: Sparkles, tone: "muted", group: "action" };

export function eventStyle(e: WorldEvent): Style {
  const base = STYLES[e.kind] ?? FALLBACK;
  if (e.kind === "plan_changed" && e.data.adaptation) return { ...base, tone: "amber" };
  if (e.kind === "llm_deliberation" && !e.data.applied) return { ...base, tone: "muted" };
  return base;
}

export const isAdaptation = (e: WorldEvent) =>
  (e.kind === "plan_changed" && e.data.adaptation === true) || (e.kind === "llm_deliberation" && e.data.applied === true);

/** Events worth a pop-up notification. */
export function isHeadline(e: WorldEvent): boolean {
  return isAdaptation(e) || [
    "story_beat", "gate_opened", "flood_warning", "chamber_flooded", "storm_warning", "director_note",
    "route_blocked", "bridge_repaired", "route_discovered", "lighthouse_activated", "help_accepted", "help_declined",
    "order_refused", "order_failed", "order_completed", "story_twist",
  ].includes(e.kind);
}

/** Map pulse colour for events that happen at a place. */
export const PULSE: Record<string, string> = {
  route_blocked: "#e0605a",
  story_twist: "#b197fc",
  trap_sprung: "#e0605a",
  bridge_repaired: "#7bc67e",
  route_cleared: "#7bc67e",
  route_discovered: "#f2a541",
  gate_opened: "#7fe3d4",
  chamber_flooded: "#4aa3df",
  flood_warning: "#4aa3df",
  lighthouse_activated: "#f2a541",
  crystal_installed: "#ffe27a",
};

/** Who wrote a line of text, stated plainly so template output is never mistaken for an LLM. */
export function authorship(e: WorldEvent): string | null {
  const by = e.data.generated_by;
  if (typeof by !== "string") return null;
  return by === "template" ? "template" : `AI · ${by}`;
}
