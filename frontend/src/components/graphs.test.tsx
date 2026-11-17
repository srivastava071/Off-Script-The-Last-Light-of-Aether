import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { RunAnalytics, RunSummary } from "../types/api";
import { AllRunsGraphs, RunGraphs } from "./GameplayGraphs";

const analytics: RunAnalytics = {
  duration: 330, deadline: null, beats_total: 2,
  progress: [{ time: 0, title: "Landing", reached: 1 }, { time: 330, title: "The beacon is lit", reached: 2 }],
  timelines: [{
    id: "kabir", name: "Kabir", color: "#4fa3d1", travel: 200, work: 100, waiting: 30,
    segments: [{ start: 10, end: 54, kind: "travel", label: "Travel to the Broken Bridge" },
      { start: 54, end: 99, kind: "work", label: "Repair bridge" }],
  }],
  decisions: [{ id: "kabir", name: "Kabir", color: "#4fa3d1", plan_changes: 7, adaptations: 1, ai_choices: 0,
    lessons_used: 0, failed_actions: 0 }],
};

const run = (id: string, mode: "default" | "game", ending: RunSummary["ending"], sim: number): RunSummary => ({
  id, mode, player_character: mode === "game" ? "aria" : null, status: "finished", ending, sim_time: sim,
  created_at: `2026-11-17T10:0${id}:00Z`, updated_at: "",
});

describe("RunGraphs", () => {
  it("draws the four gameplay graphs and explains a hovered bar", async () => {
    const { container } = render(<RunGraphs a={analytics} />);
    for (const title of ["Who did what, and when", "Mission progress over time", "How each character spent its time",
      "Decisions made by each character"]) expect(screen.getByText(title)).toBeInTheDocument();
    const work = [...container.querySelectorAll("rect")].find((r) => r.getAttribute("fill") === "#eb6834")!;
    await userEvent.hover(work);
    expect(screen.getByText(/Kabir · Repair bridge · 0:54–1:39 \(45s\)/)).toBeInTheDocument();
    expect(screen.getByText("61%")).toBeInTheDocument(); // 200 of 330 seconds travelling
  });
});

describe("AllRunsGraphs", () => {
  it("summarises every finished run", () => {
    render(<AllRunsGraphs runs={[run("1", "default", "light_returns", 330), run("2", "game", "last_storm", 600)]} />);
    expect(screen.getByText("Finished runs").previousSibling).toHaveTextContent("2");
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText("Fastest beacon").previousSibling).toHaveTextContent("5:30");
    expect(screen.getByText("How often each ending happened")).toBeInTheDocument();
  });
});
