import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { character } from "../test/fixtures";
import type { ActionOption, WorldEvent } from "../types/api";
import { ActionPanel, groupActions } from "./ActionPanel";
import { CommandBar } from "./CommandBar";
import { Storybook } from "./Storybook";
import { authorship, isAdaptation } from "./eventStyle";
import { EventTimeline } from "./EventTimeline";

const option = (type: string, label: string, available = true, reason: string | null = null): ActionOption => ({
  action: { actor: "aria", type }, label, seconds: 10, available, reason,
});

describe("ActionPanel", () => {
  it("groups what the backend offers and hides talk (it has its own panel)", () => {
    const groups = groupActions([
      option("move", "Go to Broken Bridge"), option("talk", "Talk to Kabir"), option("inspect", "Look around"),
    ]);
    expect(groups.map((g) => g.title)).toEqual(["Travel", "Other"]);
  });

  it("sends the exact action the backend offered", async () => {
    const onAct = vi.fn();
    render(<ActionPanel me={character()} options={[option("move", "Go to Broken Bridge")]} now={0} pending={false}
      lastResult={null} onAct={onAct} />);
    await userEvent.click(screen.getByRole("button", { name: /Go to Broken Bridge/ }));
    expect(onAct).toHaveBeenCalledWith({ actor: "aria", type: "move" });
  });

  it("disables unavailable actions and shows the backend's reason", () => {
    render(<ActionPanel me={character()} options={[option("repair_bridge", "Repair the Main Bridge", false, "needs Timber Planks")]}
      now={0} pending={false} lastResult={null} onAct={() => undefined} />);
    expect(screen.getByRole("button", { name: /Repair the Main Bridge/ })).toBeDisabled();
    expect(screen.getByText(/needs Timber Planks/)).toBeInTheDocument();
  });

  it("shows the real result of the last request, including rejections", () => {
    render(<ActionPanel me={character()} options={[]} now={0} pending={false} onAct={() => undefined}
      lastResult={{ ok: false, message: "The Main Bridge is broken.", events: [], completes_at: null, duplicate: false }} />);
    expect(screen.getByText(/The Main Bridge is broken/)).toBeInTheDocument();
  });

  it("explains when the player is busy instead of offering actions", () => {
    const me = character({
      location_id: null,
      travel: { route_id: "coast_road", from_location: "harbour", to_location: "bridge", depart_at: 0, arrive_at: 28, progress: 0 },
    });
    render(<ActionPanel me={me} options={[option("inspect", "Look around")]} now={14} pending={false} lastResult={null}
      onAct={() => undefined} placeName={() => "Broken Bridge"} />);
    expect(screen.getByText(/Travelling to the Broken Bridge/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Look around/ })).toBeNull();
  });
});

const ev = (over: Partial<WorldEvent>): WorldEvent => ({
  seq: 1, time: 60, kind: "arrived", description: "", actor: "kabir", location_id: null, data: {}, ...over,
});

describe("event log", () => {
  it("labels adaptations and who wrote each line", () => {
    expect(isAdaptation(ev({ kind: "plan_changed", data: { adaptation: true } }))).toBe(true);
    expect(isAdaptation(ev({ kind: "plan_changed", data: { adaptation: false } }))).toBe(false);
    expect(authorship(ev({ data: { generated_by: "template" } }))).toBe("template");
    expect(authorship(ev({ data: { generated_by: "groq:qwen" } }))).toBe("AI · groq:qwen");
  });

  it("filters to adaptations", async () => {
    render(<EventTimeline events={[
      ev({ seq: 1, kind: "arrived", description: "Kabir arrives at Broken Bridge." }),
      ev({ seq: 2, kind: "plan_changed", description: "Kabir adapts — the bridge is blocked.", data: { adaptation: true } }),
    ]} />);
    expect(screen.getByText(/Kabir arrives/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Adaptation" }));
    expect(screen.queryByText(/Kabir arrives/)).toBeNull();
    expect(screen.getByText(/Kabir adapts/)).toBeInTheDocument();
  });
});

describe("CommandBar", () => {
  it("sends what the player typed", async () => {
    const onCommand = vi.fn();
    render(<CommandBar disabled={false} pending={false} lastResult={null} voices={false} onVoices={() => undefined}
      onCommand={onCommand} />);
    await userEvent.type(screen.getByLabelText("Command"), "Kabir, fix the bridge");
    await userEvent.click(screen.getByRole("button", { name: "Send command" }));
    expect(onCommand).toHaveBeenCalledWith("Kabir, fix the bridge");
  });

  it("offers example commands", async () => {
    render(<CommandBar disabled={false} pending={false} lastResult={null} voices={false} onVoices={() => undefined}
      onCommand={() => undefined} />);
    await userEvent.click(screen.getByRole("button", { name: /Meera, scout the forest/ }));
    expect(screen.getByLabelText("Command")).toHaveValue("Meera, scout the forest and mark the traps");
  });

  it("shows each character's answer, including refusals", () => {
    const result = {
      ok: true, message: "1 character(s) took orders; 1 order(s) refused.", completes_at: null, duplicate: false,
      events: [
        ev({ seq: 5, kind: "order_accepted", description: 'Kabir: "Very well." Will repair the Main Bridge.' }),
        ev({ seq: 6, kind: "order_refused", description: "Meera cannot: Meera cannot repair the Main Bridge." }),
      ],
    };
    render(<CommandBar disabled={false} pending={false} lastResult={result} voices={false} onVoices={() => undefined}
      onCommand={() => undefined} />);
    expect(screen.getByText(/Will repair the Main Bridge/)).toBeInTheDocument();
    expect(screen.getByText(/Meera cannot repair/)).toBeInTheDocument();
  });
});

describe("CommandBar tabs (Do / Say / Story)", () => {
  const twists = { used: 1, max: 3, ready_at: null, examples: ["A fallen tree blocks the Coast Road."] };
  const bar = (over: Partial<Parameters<typeof CommandBar>[0]> = {}) => (
    <CommandBar disabled={false} pending={false} lastResult={null} voices={false} onVoices={() => undefined}
      onCommand={() => undefined} onSay={() => undefined} onTwist={() => undefined} twists={twists} now={0} {...over} />
  );

  it("sends Say messages to the radio, not as orders", async () => {
    const onSay = vi.fn();
    const onCommand = vi.fn();
    render(bar({ onSay, onCommand }));
    await userEvent.click(screen.getByRole("tab", { name: /Say/ }));
    await userEvent.type(screen.getByLabelText("Say"), "How is everyone?");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(onSay).toHaveBeenCalledWith("How is everyone?");
    expect(onCommand).not.toHaveBeenCalled();
  });

  it("writes twists from the Story tab and shows how many are left", async () => {
    const onTwist = vi.fn();
    render(bar({ onTwist }));
    await userEvent.click(screen.getByRole("tab", { name: /Story/ }));
    expect(screen.getByText(/2 of 3 twists left/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /A fallen tree blocks the Coast Road/ }));
    await userEvent.click(screen.getByRole("button", { name: "Add twist" }));
    expect(onTwist).toHaveBeenCalledWith("A fallen tree blocks the Coast Road.");
  });

  it("closes the Story tab during the cooldown", async () => {
    render(bar({ twists: { ...twists, ready_at: 30 }, now: 10 }));
    await userEvent.click(screen.getByRole("tab", { name: /Story/ }));
    expect(screen.getByLabelText("Story twist")).toBeDisabled();
    expect(screen.getByText(/next in 20s/)).toBeInTheDocument();
  });
});

describe("Storybook", () => {
  it("labels who wrote each page", () => {
    render(<Storybook chapters={[
      { id: 1, time: 0, title: "Landing", text: "The boat bumped the pier.", kind: "beat", generated_by: "template" },
      { id: 2, time: 9, title: "A twist in the tale", text: "A tree fell.", kind: "twist", generated_by: "groq:qwen" },
    ]} />);
    expect(screen.getByText("The boat bumped the pier.")).toBeInTheDocument();
    expect(screen.getByText("template")).toBeInTheDocument();
    expect(screen.getByText("AI narrator · groq:qwen")).toBeInTheDocument();
  });
});
