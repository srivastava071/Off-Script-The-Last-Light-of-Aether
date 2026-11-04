import { CheckCircle2, Circle, Compass, Target, XCircle } from "lucide-react";

import type { StateView } from "../types/api";
import { Badge, Panel, ProgressBar } from "./ui";

const RISK = {
  on_track: { tone: "ok", label: "On track" },
  at_risk: { tone: "amber", label: "At risk" },
  failing: { tone: "danger", label: "Failing" },
} as const;

export function ObjectivePanel({ state }: { state: StateView }) {
  const { story } = state;
  const risk = RISK[story.assessment.risk];
  const reached = story.beats.filter((b) => b.reached_at !== null).length;
  return (
    <Panel title="Objective" icon={<Target size={16} />}
      actions={<Badge tone={risk.tone}>{risk.label}</Badge>}>
      <ul className="space-y-1.5 text-sm">
        {story.objectives.map((o) => (
          <li key={o.id} className="flex items-start gap-2">
            {o.status === "complete" ? <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-ok" />
              : o.status === "failed" ? <XCircle size={16} className="mt-0.5 shrink-0 text-danger" />
                : <Circle size={16} className="mt-0.5 shrink-0 text-muted" />}
            <span>
              <span className={o.optional ? "" : "font-semibold"}>{o.title}</span>
              {o.optional && <span className="ml-1 text-xs text-muted">(optional)</span>}
              {!o.optional && <span className="block text-xs text-muted">{o.description}</span>}
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-3 space-y-1">
        <div className="flex justify-between text-xs text-muted">
          <span>Story progress</span>
          <span>{reached}/{story.beats.length} beats</span>
        </div>
        <ProgressBar value={story.assessment.progress} label="Story progress" />
      </div>
      <p className="mt-3 flex gap-2 rounded-xl border-2 border-ink/20 bg-[#fff9db] p-2 text-xs leading-snug text-ink">
        <Compass size={14} className="mt-0.5 shrink-0 text-amber" />
        <span><span className="text-amber">Director:</span> {story.assessment.note}</span>
      </p>
    </Panel>
  );
}
