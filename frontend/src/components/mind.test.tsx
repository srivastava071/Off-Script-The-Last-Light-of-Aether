import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { character } from "../test/fixtures";
import type { BeliefFact, Lesson, MindView } from "../types/api";
import { MindPanel } from "./MindPanel";
import { TeamPanel } from "./TeamPanel";
import { LessonList } from "./TeamJournal";

const fact = (over: Partial<BeliefFact>): BeliefFact => ({
  kind: "route", subject: "Main Bridge", believed: "broken", actual: "open", up_to_date: false, as_of: 0,
  route_id: "main_bridge", believed_location: null, actual_location: null, ...over,
});

const mind: MindView = {
  thinking: {
    since: 60, chosen: "decode_symbols_myself", chosen_by: "lesson", trigger: null,
    thought: "Last time I waited 110s at the Temple Entrance.",
    options: [
      { strategy: "wait_at_temple", summary: "Wait at the temple.", chosen: false },
      { strategy: "decode_symbols_myself", summary: "Puzzle out the symbols myself.", chosen: true },
    ],
  },
  beliefs: [
    fact({}),
    fact({ subject: "Coast Road", believed: "open", actual: "open", up_to_date: true, route_id: "coast_road" }),
    fact({ kind: "teammate", subject: "Kabir", believed: "last seen at the Abandoned Harbour", actual: "at the Temple Entrance" }),
  ],
  outdated: 1,
  memories: [{ time: 75, text: "Meera's horn signal: the trail is open.", source: "signal", from_id: "meera", importance: 4 }],
  lessons: [{ id: 1, text: "Last time I waited 110s at the Temple Entrance.", status: "kept", used: true }],
};

describe("MindPanel", () => {
  const aria = character({ autonomous: true, mind });
  const show = () => render(<MindPanel character={aria} characters={[aria]} now={100} nameOf={(id) => id === "meera" ? "Meera" : id}
    onPick={() => {}} onBack={() => {}} />);

  it("explains the decision: who chose it, why, and the options", () => {
    show();
    expect(screen.getByText("Lesson from a past game")).toBeInTheDocument();
    expect(screen.getByText("Puzzle out the symbols myself.")).toBeInTheDocument();
    expect(screen.getByText(/the rules' first choice/)).toBeInTheDocument();
  });

  it("shows only what is out of date until asked for everything", async () => {
    show();
    expect(screen.getByText("broken")).toBeInTheDocument();
    expect(screen.queryByText("Coast Road")).not.toBeInTheDocument();
    await userEvent.click(screen.getByText("Show everything"));
    expect(screen.getByText("Coast Road")).toBeInTheDocument();
  });

  it("lists memories with who they came from, and lessons in use", () => {
    show();
    expect(screen.getByText(/Meera's signal/)).toBeInTheDocument();
    expect(screen.getByText("used in this game")).toBeInTheDocument();
  });
});

describe("TeamPanel", () => {
  it("opens a character's mind and shows how much is out of date", async () => {
    const opened: string[] = [];
    render(<TeamPanel characters={[character({ mind })]} objects={[]} placeName={(id) => id} now={0} focus={null}
      onFocus={() => {}} onOpenMind={(id) => opened.push(id)} />);
    expect(screen.getByText("1 out of date")).toBeInTheDocument();
    await userEvent.click(screen.getByText(/Look inside Aria's head/));
    expect(opened).toEqual(["aria"]);
  });
});

describe("LessonList", () => {
  it("labels kept, dropped and on-trial lessons in words, not colour alone", () => {
    const lesson = (id: number, status: Lesson["status"]): Lesson => ({
      id, character_id: "aria", character: "Aria", text: `Lesson ${id}`, evidence: "", status, result: null,
      learned_in_run: "r1", tested_in_run: null, baseline_seconds: 330, tested_seconds: null, created_at: "",
    });
    render(<LessonList lessons={[lesson(1, "kept"), lesson(2, "rejected"), lesson(3, "trying")]} />);
    expect(screen.getByText("learned")).toBeInTheDocument();
    expect(screen.getByText("dropped")).toBeInTheDocument();
    expect(screen.getByText("trying next")).toBeInTheDocument();
  });
});
