import { ScrollText } from "lucide-react";
import { useMemo, useState } from "react";

import { formatClock } from "../game/geometry";
import type { WorldEvent } from "../types/api";
import { authorship, eventStyle, isAdaptation, type EventGroup } from "./eventStyle";
import { Panel } from "./ui";

type Filter = "all" | "story" | "adapt" | "talk";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "story", label: "Story" },
  { id: "adapt", label: "Adaptation" },
  { id: "talk", label: "Dialogue" },
];

const NOISE = new Set(["waited", "action_started"]);

const TONE_TEXT: Record<string, string> = {
  muted: "text-muted", amber: "text-amber", teal: "text-teal", danger: "text-danger", ok: "text-ok", sky: "text-sky",
};

export function EventTimeline({ events, className = "" }: { events: WorldEvent[]; className?: string }) {
  const [filter, setFilter] = useState<Filter>("all");
  const shown = useMemo(() => {
    const keep = (e: WorldEvent) => {
      if (NOISE.has(e.kind)) return false;
      if (filter === "all") return true;
      if (filter === "adapt") return isAdaptation(e) || e.kind === "llm_deliberation";
      return eventStyle(e).group === (filter as EventGroup);
    };
    return events.filter(keep).slice(-150).reverse();
  }, [events, filter]);

  return (
    <Panel
      title="Event log"
      icon={<ScrollText size={16} />}
      className={`flex min-h-0 flex-col ${className}`}
      actions={
        <div className="flex gap-1" role="tablist" aria-label="Filter events">
          {FILTERS.map((f) => (
            <button key={f.id} role="tab" aria-selected={filter === f.id} onClick={() => setFilter(f.id)}
              className={`rounded-full border-2 px-2.5 py-0.5 text-xs font-bold ${filter === f.id ? "border-ink bg-[#ffd43b] text-ink" : "border-transparent text-muted hover:text-ink"}`}>
              {f.label}
            </button>
          ))}
        </div>
      }
    >
      <ol className="scroll-thin -mr-2 min-h-0 flex-1 space-y-1.5 overflow-y-auto pr-2" aria-live="polite">
        {shown.length === 0 && <li className="text-sm text-muted">Nothing yet.</li>}
        {shown.map((e) => {
          const st = eventStyle(e);
          const Icon = st.icon;
          const by = authorship(e);
          const adapt = isAdaptation(e);
          return (
            <li key={e.seq} className={`animate-rise flex gap-2 rounded-lg px-2 py-1.5 text-sm
              ${adapt ? "border border-amber/40 bg-amber/5" : "hover:bg-panel-2/60"}`}>
              <span className="w-10 shrink-0 pt-0.5 text-right font-mono text-xs text-muted">{formatClock(e.time)}</span>
              <Icon size={15} className={`mt-0.5 shrink-0 ${TONE_TEXT[st.tone]}`} aria-hidden />
              <span className="min-w-0 flex-1 leading-snug">
                {adapt && <span className="mr-1 text-xs font-semibold uppercase text-amber">Adaptation</span>}
                {e.description}
                {by && <span className="ml-1 text-xs text-muted">· {by}</span>}
                {e.kind === "plan_changed" && e.data.planner === "llm" && (
                  <span className="ml-1 text-xs text-teal">· chosen with AI</span>
                )}
              </span>
            </li>
          );
        })}
      </ol>
    </Panel>
  );
}
