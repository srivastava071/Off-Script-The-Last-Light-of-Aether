import { render, screen } from "@testing-library/react";

import { state as stateView } from "../test/fixtures";
import type { StateView } from "../types/api";
import { MissionBar, nextStep } from "./MissionBar";

const beats = (reached: string[]) =>
  ["landing", "bridge_broken", "way_across", "temple_reached", "puzzle_solved"].map((id) => ({
    id, title: id, reached_at: reached.includes(id) ? 10 : null,
  }));

const withStory = (reached: string[], note = "On track. Next: the temple mechanism is still broken.") => {
  const base = stateView();
  return { ...base, story: { ...base.story, beats: beats(reached), assessment: { ...base.story.assessment, note } } } as StateView;
};

describe("MissionBar", () => {
  it("tells a new player to cross the canyon first", () => {
    expect(nextStep(withStory(["landing"]))).toMatch(/Cross the canyon/);
  });

  it("turns the Director's note into a plain instruction once at the temple", () => {
    expect(nextStep(withStory(["landing", "way_across", "temple_reached"]))).toBe("Fix the temple lock: Kabir fits the Brass Gear");
  });

  it("falls back to the Director's own words for anything unknown", () => {
    expect(nextStep(withStory(["temple_reached"], "At risk. Next: something new happened."))).toBe("something new happened");
  });

  it("always shows the goal", () => {
    render(<MissionBar state={withStory(["landing"])} />);
    expect(screen.getByText(/Your goal|The goal/)).toBeInTheDocument();
    expect(screen.getByText("Next step")).toBeInTheDocument();
  });
});
