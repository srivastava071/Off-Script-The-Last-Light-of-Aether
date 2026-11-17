import { BarChart3, Clock, Flag, ListChecks, Loader2, Timer, Trophy } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { formatClock } from "../game/geometry";
import { api, type RunSession } from "../services/api";
import type { EndingId, RunAnalytics, RunSummary } from "../types/api";
import { Panel } from "./ui";

// Colours (validated: blue/orange and violet/aqua pass the colour-blind checks). Waiting is a neutral track.
const TRAVEL = "#2a78d6";
const WORK = "#eb6834";
const WAIT = "#e3e5ee";
const WATCH = "#6250d6";
const GAME = "#1baf7a";
const BAR = "#6250d6";
const INK = "#1d2142";
const MUTED = "#6b6f8a";
const GRID = "rgba(29,33,66,0.1)";

const ENDINGS: { id: EndingId; title: string }[] = [
  { id: "light_returns", title: "The Light Returns" },
  { id: "unexpected_route", title: "An Unexpected Route" },
  { id: "costly_victory", title: "A Costly Victory" },
  { id: "last_storm", title: "The Last Storm" },
];

/** A chart card: title, a one-line readout of whatever is hovered, then the graphic. */
function Chart({ title, readout, hint, children }: { title: string; readout: string | null; hint: string; children: ReactNode }) {
  return (
    <figure className="min-w-0 rounded-xl border-2 border-line bg-white p-3">
      <figcaption className="text-xs font-bold uppercase text-muted">{title}</figcaption>
      <p className="mb-1 min-h-[1.25rem] text-xs" aria-live="polite">{readout ?? <span className="text-muted">{hint}</span>}</p>
      {children}
    </figure>
  );
}

function Legend({ items }: { items: { color: string; label: string; square?: boolean }[] }) {
  return (
    <ul className="mt-1 flex flex-wrap gap-3 text-xs text-muted">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1">
          <span className={`inline-block size-2.5 ${i.square ? "rounded-[2px]" : "rounded-full"}`} style={{ background: i.color }} />
          {i.label}
        </li>
      ))}
    </ul>
  );
}

const ticksFor = (end: number) => {
  const step = end > 480 ? 120 : 60;
  const out = [];
  for (let t = 0; t <= end; t += step) out.push(t);
  return out;
};

// --- one run ----------------------------------------------------------------------------------------------

/** Who was doing what, and when: one lane per character, story milestones as dashed lines. */
export function ActivityTimeline({ a, W = 640 }: { a: RunAnalytics; W?: number }) {
  const [hover, setHover] = useState<string | null>(null);
  const padL = 56, padR = 12, lane = 30, top = 14;
  const H = top + a.timelines.length * lane + 24;
  const x = (t: number) => padL + (t / a.duration) * (W - padL - padR);
  return (
    <Chart title="Who did what, and when" readout={hover} hint="Hover a bar or a milestone for details.">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Timeline of each character's travel, work and waiting"
        onMouseLeave={() => setHover(null)}>
        {ticksFor(a.duration).map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={top - 4} y2={H - 20} stroke={GRID} />
            <text x={x(t)} y={H - 6} textAnchor="middle" fontSize="11" fill={MUTED}>{formatClock(t)}</text>
          </g>
        ))}
        {a.timelines.map((c, i) => {
          const y = top + i * lane;
          return (
            <g key={c.id}>
              <text x={padL - 8} y={y + 15} textAnchor="end" fontSize="12" fontWeight="bold" fill={INK}>{c.name}</text>
              <rect x={x(0)} y={y + 4} width={x(a.duration) - x(0)} height={16} rx={4} fill={WAIT}
                onMouseEnter={() => setHover(`${c.name} · waiting or deciding: ${c.waiting}s in total`)} />
              {c.segments.map((s, k) => (
                <rect key={k} x={x(s.start)} y={y + 4} width={Math.max(2, x(s.end) - x(s.start))} height={16} rx={4}
                  fill={s.kind === "travel" ? TRAVEL : WORK} stroke="#fff" strokeWidth={2}
                  onMouseEnter={() => setHover(`${c.name} · ${s.label} · ${formatClock(s.start)}–${formatClock(s.end)} (${s.end - s.start}s)`)} />
              ))}
            </g>
          );
        })}
        {a.progress.map((b) => (
          <g key={`${b.title}-${b.time}`} onMouseEnter={() => setHover(`${formatClock(b.time)} · ${b.title}`)}>
            <line x1={x(b.time)} x2={x(b.time)} y1={top - 6} y2={H - 20} stroke={INK} strokeOpacity={0.35} strokeDasharray="3 3" />
            <rect x={x(b.time) - 6} y={0} width={12} height={H - 20} fill="transparent" />
            <path d={`M${x(b.time)} ${top - 10} l4 4 l-4 4 l-4 -4 Z`} fill={INK} />
          </g>
        ))}
      </svg>
      <Legend items={[{ color: TRAVEL, label: "travelling", square: true }, { color: WORK, label: "working on a task", square: true },
        { color: WAIT, label: "waiting / deciding", square: true }, { color: INK, label: "story milestone" }]} />
    </Chart>
  );
}

/** How far the mission got over time (story beats reached), with the storm deadline in Game Mode. */
export function ProgressChart({ a, W = 640 }: { a: RunAnalytics; W?: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const H = W < 500 ? 170 : 200, padL = 36, padR = 14, padT = 12, padB = 26;
  const end = Math.max(a.duration, a.deadline ?? 0);
  const x = (t: number) => padL + (t / end) * (W - padL - padR);
  const y = (n: number) => padT + (1 - n / Math.max(1, a.beats_total)) * (H - padT - padB);
  const pts = [{ time: 0, reached: 0 }, ...a.progress];
  const d = pts.map((p, i) => (i === 0 ? `M${x(p.time)} ${y(p.reached)}` : `H${x(p.time)} V${y(p.reached)}`)).join(" ")
    + ` H${x(a.duration)}`;
  const shown = hover !== null ? a.progress[hover] : null;
  return (
    <Chart title="Mission progress over time" hint="Hover a point to see which story beat was reached."
      readout={shown ? `${formatClock(shown.time)} · ${shown.title} (${shown.reached} of ${a.beats_total})` : null}>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
        aria-label={`Mission progress: ${a.progress.length} of ${a.beats_total} story beats reached by ${formatClock(a.duration)}`}
        onMouseLeave={() => setHover(null)}>
        {[0, Math.round(a.beats_total / 2), a.beats_total].map((n) => (
          <g key={n}>
            <line x1={padL} x2={W - padR} y1={y(n)} y2={y(n)} stroke={GRID} />
            <text x={padL - 6} y={y(n) + 4} textAnchor="end" fontSize="11" fill={MUTED}>{n}</text>
          </g>
        ))}
        {ticksFor(end).map((t) => (
          <text key={t} x={x(t)} y={H - 6} textAnchor="middle" fontSize="11" fill={MUTED}>{formatClock(t)}</text>
        ))}
        {a.deadline !== null && (
          <g>
            <line x1={x(a.deadline)} x2={x(a.deadline)} y1={padT} y2={H - padB} stroke="#e03131" strokeWidth={2} strokeDasharray="5 4" />
            <text x={x(a.deadline) - 4} y={padT + 10} textAnchor="end" fontSize="11" fontWeight="bold" fill="#c92a2a">storm</text>
          </g>
        )}
        <path d={d} fill="none" stroke={TRAVEL} strokeWidth={2} strokeLinejoin="round" />
        {a.progress.map((p, i) => (
          <g key={i} onMouseEnter={() => setHover(i)}>
            <circle cx={x(p.time)} cy={y(p.reached)} r={12} fill="transparent" />
            <circle cx={x(p.time)} cy={y(p.reached)} r={hover === i ? 6 : 4.5} fill={TRAVEL} stroke="#fff" strokeWidth={2} />
          </g>
        ))}
        {a.progress.length > 0 && (
          <text x={x(a.progress[a.progress.length - 1].time) - 8} y={y(a.progress[a.progress.length - 1].reached) - 8}
            textAnchor="end" fontSize="12" fontWeight="bold" fill={INK}>
            {a.progress[a.progress.length - 1].reached}/{a.beats_total} beats
          </text>
        )}
      </svg>
      <p className="text-xs text-muted">Vertical axis: story beats reached. Horizontal axis: game time.</p>
    </Chart>
  );
}

/** How each character spent its time, as a share of the run. */
export function TimeSplit({ a, W = 640 }: { a: RunAnalytics; W?: number }) {
  const [hover, setHover] = useState<string | null>(null);
  const padL = 56, padR = 12, row = 30;
  const H = a.timelines.length * row + 6;
  const span = W - padL - padR;
  return (
    <Chart title="How each character spent its time" readout={hover} hint="Hover a part of a bar for the exact seconds.">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Share of time spent travelling, working and waiting"
        onMouseLeave={() => setHover(null)}>
        {a.timelines.map((c, i) => {
          const total = Math.max(1, c.travel + c.work + c.waiting);
          const parts = [
            { label: "travelling", v: c.travel, color: TRAVEL, text: "#fff" },
            { label: "working", v: c.work, color: WORK, text: "#fff" },
            { label: "waiting", v: c.waiting, color: WAIT, text: INK },
          ];
          let at = padL;
          const yy = i * row + 4;
          return (
            <g key={c.id}>
              <text x={padL - 8} y={yy + 15} textAnchor="end" fontSize="12" fontWeight="bold" fill={INK}>{c.name}</text>
              {parts.map((p) => {
                const w = (p.v / total) * span;
                const pct = Math.round((p.v / total) * 100);
                const el = (
                  <g key={p.label} onMouseEnter={() => setHover(`${c.name} · ${p.label}: ${p.v}s (${pct}%)`)}>
                    <rect x={at} y={yy} width={Math.max(0, w)} height={20} rx={4} fill={p.color} stroke="#fff" strokeWidth={2} />
                    {w > 34 && <text x={at + w / 2} y={yy + 14} textAnchor="middle" fontSize="11" fontWeight="bold" fill={p.text}>{pct}%</text>}
                  </g>
                );
                at += w;
                return el;
              })}
            </g>
          );
        })}
      </svg>
      <Legend items={[{ color: TRAVEL, label: "travelling", square: true }, { color: WORK, label: "working", square: true },
        { color: WAIT, label: "waiting / deciding", square: true }]} />
    </Chart>
  );
}

const METRICS = [
  { key: "plan_changes", label: "Plan changes" },
  { key: "adaptations", label: "Adaptations" },
  { key: "ai_choices", label: "AI choices" },
  { key: "lessons_used", label: "Lessons used" },
  { key: "failed_actions", label: "Failed actions" },
] as const;

/** Decisions per character: one small bar chart per kind of decision. */
export function DecisionBars({ a }: { a: RunAnalytics }) {
  const max = Math.max(1, ...a.decisions.flatMap((d) => METRICS.map((m) => d[m.key])));
  return (
    <Chart title="Decisions made by each character" readout={null} hint="How often each character changed its plan, adapted, or used the AI or a lesson.">
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
        {METRICS.map((m) => (
          <div key={m.key}>
            <p className="text-xs font-bold text-ink">{m.label}</p>
            <ul className="mt-0.5 space-y-0.5">
              {a.decisions.map((d) => (
                <li key={d.id} className="flex items-center gap-1.5 text-xs">
                  <span className="w-11 shrink-0 text-muted">{d.name}</span>
                  <span className="h-2.5 rounded-r-[4px]" style={{ width: `${(d[m.key] / max) * 70}%`, minWidth: d[m.key] ? 4 : 0, background: BAR }} />
                  <span className="font-bold">{d[m.key]}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Chart>
  );
}

/** All graphs for one run. */
export function RunGraphs({ a, wide = false }: { a: RunAnalytics; wide?: boolean }) {
  const W = wide ? 520 : 300; // drawing width: the narrow side panel gets its own layout so text stays readable
  return (
    <div className={`grid gap-3 ${wide ? "lg:grid-cols-2" : ""}`}>
      <ActivityTimeline a={a} W={W} />
      <ProgressChart a={a} W={W} />
      <TimeSplit a={a} W={W} />
      <DecisionBars a={a} />
    </div>
  );
}

/** Loads a run's analytics; ``refresh`` re-fetches it (e.g. as live game time moves on). */
export function useAnalytics(session: RunSession | null, refresh: unknown = null) {
  const [data, setData] = useState<RunAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!session) return;
    let live = true;
    api.analytics(session).then((a) => live && setData(a)).catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [session, refresh]);
  return { data, error };
}

/** Gameplay graphs for a run, inside a panel (ending screen) or bare (game side panel). */
export function RunGraphsPanel({ session, refresh, wide = false, bare = false }: {
  session: RunSession; refresh?: unknown; wide?: boolean; bare?: boolean;
}) {
  const { data, error } = useAnalytics(session, refresh);
  const body = error ? <p className="text-sm text-danger">The graphs could not be loaded: {error}</p>
    : !data ? <p className="flex justify-center text-muted"><Loader2 className="animate-spin" /></p>
    : <RunGraphs a={data} wide={wide} />;
  if (bare) return body;
  return <Panel title="Gameplay graphs" icon={<BarChart3 size={16} />}>{body}</Panel>;
}

// --- all runs ----------------------------------------------------------------------------------------------

function Tile({ icon, value, label }: { icon: ReactNode; value: string; label: string }) {
  return (
    <div className="panel p-3 text-center">
      <div className="flex items-center justify-center gap-1 text-muted">{icon}</div>
      <div className="font-display text-2xl text-amber">{value}</div>
      <div className="text-xs text-muted">{label}</div>
    </div>
  );
}

/** Every finished run: summary tiles, finish time per run, how often each ending happened, and the table. */
export function AllRunsGraphs({ runs }: { runs: RunSummary[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const ordered = [...runs].sort((p, q) => p.created_at.localeCompare(q.created_at));
  const success = ordered.filter((r) => r.ending && r.ending !== "last_storm");
  const fastest = success.length ? Math.min(...success.map((r) => r.sim_time)) : null;
  const avg = ordered.length ? Math.round(ordered.reduce((s, r) => s + r.sim_time, 0) / ordered.length) : 0;
  const counts = ENDINGS.map((e) => ({ ...e, n: ordered.filter((r) => r.ending === e.id).length }));
  const maxCount = Math.max(1, ...counts.map((c) => c.n));

  const W = 520, H = 210, padL = 40, padR = 14, padT = 12, padB = 26;
  const times = ordered.map((r) => r.sim_time);
  const lo = Math.max(0, Math.floor((Math.min(...times) - 30) / 30) * 30);
  const hi = Math.ceil((Math.max(...times) + 30) / 30) * 30;
  const x = (i: number) => padL + (ordered.length === 1 ? (W - padL - padR) / 2 : (i / (ordered.length - 1)) * (W - padL - padR));
  const y = (t: number) => padT + (1 - (t - lo) / Math.max(1, hi - lo)) * (H - padT - padB);
  const shown = hover !== null ? ordered[hover] : null;
  const titleOf = (id: EndingId | null) => ENDINGS.find((e) => e.id === id)?.title ?? "—";

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile icon={<Flag size={16} />} value={String(ordered.length)} label="Finished runs" />
        <Tile icon={<Trophy size={16} />} value={`${ordered.length ? Math.round((success.length / ordered.length) * 100) : 0}%`} label="Beacon lit (any good ending)" />
        <Tile icon={<Timer size={16} />} value={fastest !== null ? formatClock(fastest) : "—"} label="Fastest beacon" />
        <Tile icon={<Clock size={16} />} value={formatClock(avg)} label="Average run length" />
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <Chart title="Game length per run (oldest to newest)" hint="Hover a point for that run's ending."
          readout={shown ? `Run ${hover! + 1} · ${shown.mode === "game" ? `Game Mode (${shown.player_character})` : "Watch"} · ${titleOf(shown.ending)} at ${formatClock(shown.sim_time)}` : null}>
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Game length of each finished run"
            onMouseLeave={() => setHover(null)}>
            {[lo, Math.round((lo + hi) / 60) * 30, hi].map((t) => (
              <g key={t}>
                <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke={GRID} />
                <text x={padL - 6} y={y(t) + 4} textAnchor="end" fontSize="11" fill={MUTED}>{formatClock(t)}</text>
              </g>
            ))}
            {ordered.map((r, i) => {
              const color = r.mode === "game" ? GAME : WATCH;
              return (
                <g key={r.id} onMouseEnter={() => setHover(i)}>
                  <circle cx={x(i)} cy={y(r.sim_time)} r={12} fill="transparent" />
                  {r.mode === "game"
                    ? <rect x={x(i) - 5} y={y(r.sim_time) - 5} width={10} height={10} rx={2} fill={color} stroke="#fff" strokeWidth={2} />
                    : <circle cx={x(i)} cy={y(r.sim_time)} r={hover === i ? 6.5 : 5} fill={color} stroke="#fff" strokeWidth={2} />}
                </g>
              );
            })}
            <text x={W - padR} y={H - 6} textAnchor="end" fontSize="11" fill={MUTED}>newest →</text>
          </svg>
          <Legend items={[{ color: WATCH, label: "Watch run" }, { color: GAME, label: "Game Mode run", square: true }]} />
        </Chart>

        <Chart title="How often each ending happened" readout={null} hint="Across all finished runs.">
          <ul className="space-y-2 pt-1">
            {counts.map((c) => (
              <li key={c.id} className="text-xs">
                <p className="mb-0.5 font-bold text-ink">{c.title}</p>
                <div className="flex items-center gap-2">
                  <span className="h-4 rounded-r-[4px]" style={{ width: `${(c.n / maxCount) * 80}%`, minWidth: c.n ? 4 : 0, background: BAR }} />
                  <span className="font-bold">{c.n}</span>
                </div>
              </li>
            ))}
          </ul>
        </Chart>
      </div>

      <details className="rounded-xl border-2 border-line bg-white p-3 text-sm">
        <summary className="flex cursor-pointer items-center gap-1 font-bold"><ListChecks size={14} /> Table of all runs</summary>
        <table className="mt-2 w-full text-left text-xs">
          <thead><tr className="text-muted"><th className="py-1">#</th><th>Mode</th><th>Player</th><th>Ending</th><th>Length</th></tr></thead>
          <tbody>
            {ordered.map((r, i) => (
              <tr key={r.id} className="border-t border-line">
                <td className="py-1">{i + 1}</td>
                <td>{r.mode === "game" ? "Game" : "Watch"}</td>
                <td>{r.player_character ?? "—"}</td>
                <td>{titleOf(r.ending)}</td>
                <td>{formatClock(r.sim_time)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
