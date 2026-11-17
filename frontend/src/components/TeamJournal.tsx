import { BookOpen, CheckCircle2, FlaskConical, Loader2, RotateCcw, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../services/api";
import type { Journal, JournalRun, Lesson } from "../types/api";
import { Badge, Button, Panel } from "./ui";

const STATUS: Record<Lesson["status"], { label: string; tone: "ok" | "danger" | "amber"; icon: typeof CheckCircle2 }> = {
  kept: { label: "learned", tone: "ok", icon: CheckCircle2 },
  rejected: { label: "dropped", tone: "danger", icon: XCircle },
  trying: { label: "trying next", tone: "amber", icon: FlaskConical },
};

/** Loads the team journal; ``refreshKey`` reloads it (e.g. after a run ends). */
export function useJournal(refreshKey: unknown = null) {
  const [journal, setJournal] = useState<Journal | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    api.journal().then((j) => live && setJournal(j)).catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [refreshKey]);
  return { journal, setJournal, error };
}

/** The team journal: what the characters learned across Watch runs, and the learning curve. */
export function TeamJournal() {
  const { journal, setJournal, error } = useJournal();
  const [resetting, setResetting] = useState(false);

  const reset = async () => {
    if (!window.confirm("Forget every lesson? The next Watch run will play with the rules alone.")) return;
    setResetting(true);
    try {
      setJournal(await api.resetJournal());
    } finally {
      setResetting(false);
    }
  };

  if (error) return <p className="text-center text-sm text-danger">The team journal could not be loaded: {error}</p>;
  if (!journal) return <p className="flex justify-center text-muted"><Loader2 className="animate-spin" /></p>;

  const watch = journal.runs.filter((r) => r.mode === "default");
  return (
    <Panel title="Team journal: learning across games" icon={<BookOpen size={16} />}
      actions={journal.lessons.length > 0 || journal.runs.length > 0 ? (
        <Button variant="danger" onClick={() => void reset()} disabled={resetting} className="!px-2 !py-1 text-xs">
          <RotateCcw size={12} /> Forget everything
        </Button>
      ) : undefined}>
      <p className="mb-3 text-sm text-muted">
        After every <b>Watch</b> run, each character looks back at where it stood waiting while it could have done
        something else, and writes one lesson to try next time. The next Watch run tests it: if the beacon is lit sooner
        (or with a better ending) the lesson is kept, otherwise it is dropped. Lessons can only pick moves the rules
        already allow.
      </p>
      {watch.length === 0 ? (
        <p className="rounded-xl border-2 border-dashed border-line p-4 text-center text-sm text-muted">
          No Watch runs yet. Press <b>Watch the AI play</b>, let it finish, then watch again to see the team learn.
        </p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <LearningCurve runs={watch} lessons={journal.lessons} />
          <LessonList lessons={journal.lessons} />
        </div>
      )}
    </Panel>
  );
}

export function LessonList({ lessons }: { lessons: Lesson[] }) {
  if (lessons.length === 0) return <p className="text-sm text-muted">No lessons yet.</p>;
  return (
    <ul className="space-y-2">
      {[...lessons].reverse().map((l) => {
        const s = STATUS[l.status];
        const Icon = s.icon;
        return (
          <li key={l.id} className="rounded-xl border-2 border-line bg-white p-2.5 text-sm leading-snug">
            <div className="mb-1 flex items-center gap-1.5">
              <b>{l.character}</b>
              <Badge tone={s.tone}><Icon size={12} /> {s.label}</Badge>
            </div>
            <p>“{l.text}”</p>
            {l.result && <p className="mt-1 text-xs text-muted">{l.result}</p>}
          </li>
        );
      })}
    </ul>
  );
}

/** Finish time of each Watch run (lower is better). Runs that tested a lesson are marked kept or dropped. */
function LearningCurve({ runs, lessons }: { runs: JournalRun[]; lessons: Lesson[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 420;
  const H = 190;
  const pad = { l: 44, r: 14, t: 16, b: 30 };
  const times = runs.map((r) => r.finished_at);
  const lo = Math.floor((Math.min(...times) - 15) / 10) * 10;
  const hi = Math.ceil((Math.max(...times) + 15) / 10) * 10;
  const x = (i: number) => pad.l + (runs.length === 1 ? (W - pad.l - pad.r) / 2 : (i * (W - pad.l - pad.r)) / (runs.length - 1));
  const y = (t: number) => pad.t + ((t - lo) / (hi - lo || 1)) * (H - pad.t - pad.b);
  const tested = (r: JournalRun) => lessons.find((l) => l.tested_in_run === r.run_id);
  const ticks = [lo, Math.round((lo + hi) / 20) * 10, hi];
  const shown = hover !== null ? runs[hover] : null;

  return (
    <figure className="relative">
      <figcaption className="mb-1 text-xs font-bold uppercase text-muted">Seconds to light the beacon, per Watch run (lower is better)</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
        aria-label={`Learning curve: ${runs.map((r, i) => `run ${i + 1} ${r.finished_at}s`).join(", ")}`}
        onMouseLeave={() => setHover(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="#1d2142" strokeOpacity={0.1} />
            <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill="#6b6f8a">{t}s</text>
          </g>
        ))}
        <polyline fill="none" stroke="#1d2142" strokeWidth={2} strokeLinejoin="round"
          points={runs.map((r, i) => `${x(i)},${y(r.finished_at)}`).join(" ")} />
        {runs.map((r, i) => {
          const t = tested(r);
          const fill = t?.status === "kept" ? "#2f9e44" : t?.status === "rejected" ? "#e03131" : "#ffd43b";
          return (
            <g key={r.run_id} onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)} tabIndex={0}>
              <circle cx={x(i)} cy={y(r.finished_at)} r={16} fill="transparent" />
              <circle cx={x(i)} cy={y(r.finished_at)} r={hover === i ? 7 : 5.5} fill={fill} stroke="#fff" strokeWidth={2} />
              <text x={x(i)} y={H - 10} textAnchor="middle" fontSize="11" fill="#6b6f8a">run {i + 1}</text>
            </g>
          );
        })}
        {runs.length > 1 && (
          <text x={x(runs.length - 1)} y={y(runs[runs.length - 1].finished_at) - 12} textAnchor="end" fontSize="12"
            fontWeight="bold" fill="#1d2142">{runs[runs.length - 1].finished_at}s</text>
        )}
      </svg>
      <div className="mt-1 flex flex-wrap gap-3 text-xs text-muted">
        <span className="flex items-center gap-1"><CheckCircle2 size={12} className="text-ok" /> lesson tested and kept</span>
        <span className="flex items-center gap-1"><XCircle size={12} className="text-danger" /> lesson tested and dropped</span>
      </div>
      {shown && (
        <div className="pointer-events-none absolute left-2 right-2 top-6 rounded-xl border-2 border-ink bg-white p-2 text-xs shadow-[0_3px_0_#1d2142]">
          <b>Run {hover! + 1}</b> · {shown.ending_title} at {shown.finished_at}s
          <p className="mt-0.5 text-muted">{shown.note || "Recorded."}</p>
        </div>
      )}
    </figure>
  );
}
