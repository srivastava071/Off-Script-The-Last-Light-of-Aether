import type { WorldEvent } from "../types/api";
import { bubbleFor } from "./bubbles";

const ev = (over: Partial<WorldEvent>): WorldEvent => ({
  seq: 1, time: 0, kind: "arrived", description: "", actor: "kabir", location_id: null, data: {}, ...over,
});

describe("speech bubbles", () => {
  it("speaks the character's actual acknowledgement", () => {
    const b = bubbleFor(ev({ kind: "order_accepted", description: 'Kabir: "Very well. I\'ll see to it properly." Will repair.' }));
    expect(b).toEqual({ characterId: "kabir", text: "Very well. I'll see to it properly.", style: "speech" });
  });

  it("shouts when a character adapts and shows thoughts for AI choices", () => {
    expect(bubbleFor(ev({ kind: "plan_changed", data: { adaptation: true } }))?.style).toBe("shout");
    expect(bubbleFor(ev({ kind: "plan_changed", data: { adaptation: false } }))).toBeNull();
    const t = bubbleFor(ev({ kind: "llm_deliberation", description: 'Kabir weighs the options: "Clear it first." Choice: x', data: { applied: true } }));
    expect(t).toMatchObject({ text: "Clear it first.", style: "think" });
  });

  it("reacts to good and bad moments", () => {
    expect(bubbleFor(ev({ kind: "bridge_repaired" }))?.style).toBe("yay");
    expect(bubbleFor(ev({ kind: "trap_sprung" }))).toMatchObject({ text: "Ouch!!", style: "oops" });
    expect(bubbleFor(ev({ kind: "item_picked_up", data: { object_id: "sun_crystal" } }))?.text).toBe("Got the crystal!");
    expect(bubbleFor(ev({ kind: "item_picked_up", data: { object_id: "brass_gear" } }))).toBeNull();
  });

  it("keeps bubbles short and ignores events with nobody to speak", () => {
    const long = bubbleFor(ev({ kind: "talked", data: { reply: true, message: "word ".repeat(40) } }));
    expect(long!.text.length).toBeLessThanOrEqual(70);
    expect(bubbleFor(ev({ kind: "storm_warning", actor: null }))).toBeNull();
  });
});
