import type { WorldEvent } from "../types/api";

export type BubbleStyle = "speech" | "shout" | "oops" | "yay" | "think";

export interface Bubble {
  characterId: string;
  text: string;
  style: BubbleStyle;
}

const MAX = 70;

function short(text: string): string {
  const clean = text.replace(/\s+/g, " ").trim();
  return clean.length > MAX ? `${clean.slice(0, MAX - 1).trimEnd()}…` : clean;
}

function quoted(text: string): string | null {
  const m = text.match(/"([^"]+)"/);
  return m ? m[1] : null;
}

const CHEERS: Record<string, [string, BubbleStyle]> = {
  bridge_repaired: ["Fixed it!", "yay"],
  mechanism_repaired: ["Gear fitted!", "yay"],
  symbols_decoded: ["Solved it!", "yay"],
  gate_opened: ["It's open!", "shout"],
  route_discovered: ["A hidden path!", "shout"],
  traps_marked: ["Traps marked!", "yay"],
  route_blocked: ["Blocked!", "shout"],
  route_cleared: ["All clear!", "yay"],
  crystal_installed: ["In it goes!", "yay"],
  lighthouse_activated: ["Light's on! Yay!", "yay"],
  lighthouse_repaired: ["Lamp's ready!", "yay"],
  trap_sprung: ["Ouch!!", "oops"],
  action_failed: ["Oops…", "oops"],
  order_failed: ["Uh-oh, I can't…", "oops"],
  order_refused: ["I can't do that!", "oops"],
  order_completed: ["Done!", "yay"],
  help_declined: ["No way.", "oops"],
};

/** What a character says out loud (in a cartoon speech bubble) when this event happens, if anything. */
export function bubbleFor(e: WorldEvent): Bubble | null {
  const who = e.actor;
  if (!who) return null;
  switch (e.kind) {
    case "order_accepted":
    case "help_accepted":
      return { characterId: who, text: short(quoted(e.description) ?? "Let's go!"), style: "speech" };
    case "plan_changed":
      return e.data.adaptation ? { characterId: who, text: "Change of plan!", style: "shout" } : null;
    case "llm_deliberation":
      return e.data.applied ? { characterId: who, text: short(quoted(e.description) ?? "Hmm…"), style: "think" } : null;
    case "talked":
      return e.data.reply ? { characterId: who, text: short(String(e.data.message ?? "")), style: "speech" } : null;
    case "signalled":
      return { characterId: who, text: short(`📯 ${String(e.data.message ?? "Listen up, team!")}`), style: "speech" };
    case "item_picked_up":
      return e.data.object_id === "sun_crystal" ? { characterId: who, text: "Got the crystal!", style: "yay" } : null;
    default: {
      const cheer = CHEERS[e.kind];
      return cheer ? { characterId: who, text: cheer[0], style: cheer[1] } : null;
    }
  }
}
