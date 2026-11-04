import { Flag, Footprints, Target } from "lucide-react";

import type { StateView } from "../types/api";

const RISK = {
  on_track: { label: "On track", cls: "border-ok bg-[#ebfbee] text-ok" },
  at_risk: { label: "At risk", cls: "border-amber bg-[#fff4e6] text-amber" },
  failing: { label: "In trouble", cls: "border-danger bg-[#fff5f5] text-danger" },
} as const;

/** The Director's "what is still missing" turned into a plain next step a first-time player can act on. */
const NEXT_STEP: Record<string, string> = {
  "the temple mechanism is still broken": "Fix the temple lock: Kabir fits the Brass Gear",
  "the temple symbols are not decoded": "Decode the temple symbols: Meera's job",
  "nobody has opened the temple gate": "Pull the temple lever to open the gate",
  "the sun crystal is still in the chamber": "Grab the Sun Crystal before the chamber floods",
  "the lighthouse mechanism is not repaired": "Repair the lighthouse: Kabir's job",
  "the sun crystal has not reached the lighthouse": "Carry the Sun Crystal to the Lighthouse",
  "the beacon has not been lit": "Light the beacon at the Lighthouse",
};

export function nextStep(state: StateView): string {
  const reached = (id: string) => state.story.beats.some((b) => b.id === id && b.reached_at !== null);
  if (!reached("temple_reached")) {
    return reached("way_across")
      ? "Head to the Temple Entrance"
      : "Cross the canyon: Kabir fixes the bridge, Aria climbs, or Meera finds the hidden trail";
  }
  const note = state.story.assessment.note;
  const missing = note.includes("Next: ") ? note.split("Next: ")[1] : note.replace(/^Failing\. /, "");
  const key = missing.split(".")[0].trim().toLowerCase();
  return NEXT_STEP[key] ?? missing.replace(/\.$/, "");
}

/** Always-visible answer to "what am I doing?": the goal, how far the story has come, and the next step. */
export function MissionBar({ state }: { state: StateView }) {
  const { story, run } = state;
  const beats = story.beats;
  const reachedCount = beats.filter((b) => b.reached_at !== null).length;
  const current = [...beats].reverse().find((b) => b.reached_at !== null);
  const risk = RISK[story.assessment.risk];
  const game = run.mode === "game";
  const done = run.status === "finished";

  return (
    <section aria-label="Mission" className="panel flex flex-col gap-2.5 px-4 py-3 lg:flex-row lg:items-center lg:gap-6 lg:py-2">
      <div className="flex min-w-0 items-start gap-2.5 lg:max-w-[34%]">
        <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full border-[2.5px] border-ink bg-[#ffd43b] lg:size-7">
          <Target size={16} aria-hidden />
        </span>
        <p className="text-sm leading-snug">
          <b className="font-display">{game ? "Your goal" : "The goal"}</b>
          <span className="block text-muted sm:hidden">Sun Crystal → Lighthouse{game ? ", before the storm" : ""}</span>
          <span className="hidden text-muted sm:block lg:line-clamp-1">
            Bring the <b className="text-ink">Sun Crystal</b> to the <b className="text-ink">Lighthouse</b>
            {game ? " before the storm." : ". Watch the team do it alone."}
          </span>
        </p>
      </div>

      <div className="min-w-0 flex-1">
        <ol className="flex items-center" aria-label={`Story progress: ${reachedCount} of ${beats.length}`}>
          {beats.map((b, i) => {
            const on = b.reached_at !== null;
            const isCurrent = b.id === current?.id;
            return (
              <li key={b.id} className="flex flex-1 items-center last:flex-none" title={b.title}>
                <span className={`grid shrink-0 place-items-center rounded-full border-[2.5px] border-ink transition-all
                  ${isCurrent ? "size-6 bg-[#ffd43b] shadow-[0_0_0_4px_rgba(255,212,59,0.35)]" : on ? "size-3.5 bg-[#51cf66]" : "size-3.5 bg-white"}`}>
                  {isCurrent && <Footprints size={11} aria-hidden />}
                  {i === beats.length - 1 && !isCurrent && <Flag size={8} aria-hidden className={on ? "" : "text-muted"} />}
                </span>
                {i < beats.length - 1 && (
                  <span className={`h-[3px] flex-1 ${beats[i + 1].reached_at !== null ? "bg-[#51cf66]" : "bg-ink/20"}`} />
                )}
              </li>
            );
          })}
        </ol>
        <p className="mt-1.5 hidden truncate text-xs text-muted sm:block [@media(max-height:800px)]:lg:hidden">
          <span className="font-bold text-ink">Now:</span> {current?.title ?? "The adventure begins"}
        </p>
      </div>

      {!done && (
        <div className="flex min-w-0 items-center gap-2 lg:max-w-[34%]">
          <span className={`shrink-0 rounded-full border-2 px-2 py-0.5 text-xs font-bold ${risk.cls}`}>{risk.label}</span>
          <p className="text-sm leading-snug">
            <b className="font-display">Next step</b>
            <span className="block text-muted lg:line-clamp-2">{nextStep(state)}</span>
          </p>
        </div>
      )}
    </section>
  );
}
