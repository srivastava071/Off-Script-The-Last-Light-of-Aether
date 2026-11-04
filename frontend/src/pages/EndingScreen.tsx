import { BookOpen, CheckCircle2, CloudLightning, Compass, Cpu, Home, Lightbulb, Map, RotateCcw, ScrollText, Sparkles, Swords, XCircle } from "lucide-react";

import { StorybookPages } from "../components/Storybook";
import { Badge, Button, Panel } from "../components/ui";
import { formatClock } from "../game/geometry";
import type { EndingId, StateView } from "../types/api";

const ENDING_ART: Record<EndingId, { icon: typeof Sparkles; tone: string; tagline: string }> = {
  light_returns: { icon: Sparkles, tone: "text-amber", tagline: "Ending A" },
  costly_victory: { icon: Swords, tone: "text-amber", tagline: "Ending B" },
  unexpected_route: { icon: Compass, tone: "text-teal", tagline: "Ending C" },
  last_storm: { icon: CloudLightning, tone: "text-danger", tagline: "Ending D" },
};

const STAT_LABELS: Record<string, string> = {
  simulated_seconds: "Simulated time",
  adaptations: "Adaptations",
  replans: "Plan changes",
  failed_actions: "Failed actions",
  blocked_route_events: "Routes blocked",
  traps_sprung: "Traps sprung",
};

export function EndingScreen({ state, onRestart, onMenu, onOtherMode }: {
  state: StateView;
  onRestart: () => void;
  onMenu: () => void;
  onOtherMode: () => void;
}) {
  const ending = state.story.ending!;
  const art = ENDING_ART[ending.ending];
  const Icon = art.icon;
  const names = Object.fromEntries(state.characters.map((c) => [c.id, c]));
  const ai = state.story.ai;
  const live = state.run.ai_mode === "live";

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <section className="animate-rise text-center">
        <Icon size={44} className={`mx-auto ${art.tone}`} aria-hidden />
        <h1 className={`mt-1 font-display text-5xl font-bold sm:text-6xl ${ending.main_success ? "text-[#ffd43b]" : "text-[#ff8787]"} glow-text`}>{ending.title}</h1>
        <div className="mt-3 flex justify-center">
          {ending.main_success
            ? <Badge tone="ok"><CheckCircle2 size={12} /> Main objective achieved</Badge>
            : <Badge tone="danger"><XCircle size={12} /> Main objective failed</Badge>}
        </div>
        <p className="mx-auto mt-4 max-w-2xl text-lg">{ending.explanation}</p>
        <p className="mx-auto mt-2 max-w-2xl text-muted">{ending.summary}</p>
        {ending.narration ? (
          <blockquote className="mx-auto mt-5 max-w-2xl rounded-2xl border-[2.5px] border-ink bg-[#fff9db] px-5 py-3 text-left italic">
            {ending.narration}
            <footer className="mt-1 text-xs not-italic text-muted">Epilogue written by AI · {ending.narrated_by}</footer>
          </blockquote>
        ) : live ? (
          <p className="mt-4 text-xs text-muted">The narrator is writing an epilogue…</p>
        ) : null}
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Button variant="primary" onClick={onRestart}><RotateCcw size={14} /> Play again</Button>
          <Button onClick={onOtherMode}>{state.run.mode === "game" ? "Watch Default Mode" : "Play Game Mode"}</Button>
          <Button onClick={onMenu}><Home size={14} /> Main menu</Button>
        </div>
      </section>

      <div className="mt-10 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {Object.entries(STAT_LABELS).map(([k, label]) => (
          <div key={k} className="panel p-3 text-center">
            <div className="font-display text-2xl text-amber">
              {k === "simulated_seconds" ? formatClock(ending.stats[k] ?? 0) : ending.stats[k] ?? 0}
            </div>
            <div className="text-xs text-muted">{label}</div>
          </div>
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Panel title="Objectives" icon={<CheckCircle2 size={16} />}>
          <ul className="space-y-1.5 text-sm">
            {ending.objectives.map((o) => (
              <li key={o.id} className="flex items-center gap-2">
                {o.status === "complete" ? <CheckCircle2 size={16} className="text-ok" /> : <XCircle size={16} className="text-danger" />}
                {o.title} {o.optional && <span className="text-xs text-muted">(optional)</span>}
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Routes taken" icon={<Map size={16} />}>
          <ul className="space-y-2 text-sm">
            {Object.entries(ending.routes).map(([cid, stops]) => (
              <li key={cid}>
                <span className="font-semibold" style={{ color: names[cid]?.color }}>{names[cid]?.name ?? cid}</span>
                {cid === state.run.player_character && <span className="ml-1 text-xs text-amber">(you)</span>}
                <p className="text-xs text-muted">{stops.join(" → ")}</p>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="How the characters adapted" icon={<Lightbulb size={16} />}>
          {ending.adaptations.length === 0 ? (
            <p className="text-sm text-muted">Nothing forced a change of plan — the story followed its course.</p>
          ) : (
            <ul className="space-y-1.5 text-sm">{ending.adaptations.map((a) => <li key={a}>{a}</li>)}</ul>
          )}
        </Panel>

        <Panel title="AI usage" icon={<Cpu size={16} />}>
          {live ? (
            <ul className="grid grid-cols-2 gap-1 text-sm">
              <li>LLM calls: <b>{ai.calls_succeeded}</b></li>
              <li>Avg latency: <b>{ai.calls_succeeded ? Math.round(ai.total_latency_ms / ai.calls_succeeded) : 0} ms</b></li>
              <li>Deliberations used: <b>{ai.deliberations_applied}</b> / {ai.deliberations_requested}</li>
              <li>Fallbacks: <b>{ai.fallbacks}</b></li>
              <li>LLM replies: <b>{ai.llm_replies}</b></li>
              <li>Template replies: <b>{ai.template_replies}</b></li>
              <li className="col-span-2 text-xs text-muted">{Object.entries(ai.providers).map(([p, n]) => `${p} ×${n}`).join(" · ")}</li>
            </ul>
          ) : (
            <p className="text-sm text-muted">Mock mode: every decision came from the rule-based planner and every reply from templates. No LLM was used.</p>
          )}
        </Panel>
      </div>

      {(state.story.chapters ?? []).length > 0 && (
        <Panel title="The whole storybook" icon={<BookOpen size={16} />} className="mt-4">
          <StorybookPages chapters={state.story.chapters} />
          {ending.narration && (
            <article className="mt-2 rounded-xl border-2 border-amber/60 bg-[#fff4e6] p-3">
              <h3 className="font-display text-sm">The End · {ending.title}</h3>
              <p className="mt-1 text-sm leading-relaxed">{ending.narration}</p>
            </article>
          )}
        </Panel>
      )}

      <Panel title="Timeline of key events" icon={<ScrollText size={16} />} className="mt-4">
        <ol className="scroll-thin max-h-96 space-y-1 overflow-y-auto text-sm">
          {ending.key_events.map((e, i) => <li key={i} className="text-muted"><span className="text-parchment">{e}</span></li>)}
        </ol>
      </Panel>
    </div>
  );
}
