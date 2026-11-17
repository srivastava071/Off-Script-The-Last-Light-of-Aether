import {
  ArrowLeft, BookOpen, Brain, Check, Eye, Hand, ListChecks, Megaphone, Radio, ScrollText, TriangleAlert, Users,
} from "lucide-react";
import { useState, type ReactNode } from "react";

import type { BeliefFact, CharacterView, MindMemory, Thinking } from "../types/api";
import { ToonAvatar } from "./ToonAvatar";
import { Badge, Panel } from "./ui";

const age = (now: number, asOf: number | null) =>
  asOf === null ? "never seen" : now - asOf <= 0 ? "just now" : `${Math.round(now - asOf)}s ago`;

const CHOSEN_BY: Record<Thinking["chosen_by"], { label: string; icon: ReactNode; tone: "muted" | "teal" | "amber" | "sky" }> = {
  rules: { label: "Chosen by its rules", icon: <ListChecks size={12} />, tone: "muted" },
  ai: { label: "Chosen by the AI", icon: <Brain size={12} />, tone: "teal" },
  lesson: { label: "Lesson from a past game", icon: <BookOpen size={12} />, tone: "amber" },
  player: { label: "Your radio order", icon: <Radio size={12} />, tone: "sky" },
};

const MEMORY_ICON: Record<string, ReactNode> = {
  saw: <Eye size={13} />, did: <Hand size={13} />, told: <Radio size={13} />, signal: <Megaphone size={13} />,
  briefing: <ScrollText size={13} />,
};

/** Mind View: why a character chose its plan, and how its picture of the island differs from reality. */
export function MindPanel({ character, characters, now, nameOf, onPick, onBack }: {
  character: CharacterView;
  characters: CharacterView[];
  now: number;
  nameOf: (id: string) => string;
  onPick: (id: string) => void;
  onBack: () => void;
}) {
  const { mind } = character;
  const [all, setAll] = useState(false);
  const world = mind.beliefs.filter((b) => b.kind !== "teammate");
  const shown = all ? world : world.filter((b) => !b.up_to_date);
  const teammates = mind.beliefs.filter((b) => b.kind === "teammate");

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <button type="button" onClick={onBack} aria-label="Back to the team"
          className="grid size-8 place-items-center rounded-lg border-2 border-ink bg-white hover:bg-panel-2">
          <ArrowLeft size={15} />
        </button>
        <div className="flex gap-1" role="tablist" aria-label="Whose mind">
          {characters.map((c) => (
            <button key={c.id} type="button" role="tab" aria-selected={c.id === character.id} onClick={() => onPick(c.id)}
              title={`Look inside ${c.name}'s head`}
              className={`rounded-full border-2 p-0.5 transition ${c.id === character.id ? "border-[#7048e8] bg-[#f3f0ff]" : "border-transparent opacity-60 hover:opacity-100"}`}>
              <ToonAvatar id={c.id} color={c.color} size={28} />
            </button>
          ))}
        </div>
      </div>

      <header className="rounded-xl border-[2.5px] border-[#7048e8] bg-[#f3f0ff] p-3">
        <p className="flex items-center gap-1.5 font-display text-lg leading-tight text-[#5f3dc4]">
          <Brain size={18} /> Inside {character.name}'s head
        </p>
        <p className="mt-1 text-xs text-muted">
          {character.name} acts only on what {character.name} knows. On the map, purple bubbles and ghosts show where that
          picture of the island is out of date.
        </p>
      </header>

      <Panel title="Why this plan?" icon={<ListChecks size={16} />}>
        {!character.autonomous ? (
          <p className="text-sm text-muted">This is you: your decisions are your own.</p>
        ) : mind.thinking ? (
          <ThinkingCard thinking={mind.thinking} now={now} />
        ) : (
          <p className="text-sm text-muted">{character.name} has not made a decision yet.</p>
        )}
      </Panel>

      <Panel title="Believes vs reality" icon={<Eye size={16} />}
        actions={
          <button type="button" onClick={() => setAll(!all)} className="text-xs font-bold text-sky hover:underline">
            {all ? "Only differences" : "Show everything"}
          </button>
        }>
        {shown.length === 0 ? (
          <p className="flex items-center gap-1.5 text-sm text-ok"><Check size={15} /> Everything {character.name} knows is up to date.</p>
        ) : (
          <ul className="space-y-1.5">{shown.map((b) => <BeliefRow key={`${b.kind}:${b.subject}`} fact={b} now={now} />)}</ul>
        )}
        <p className="mb-1 mt-3 flex items-center gap-1 text-xs font-bold uppercase text-muted"><Users size={12} /> Teammates</p>
        <ul className="space-y-1 text-xs">
          {teammates.map((b) => (
            <li key={b.subject} className="flex flex-wrap gap-x-1">
              <b>{b.subject}:</b>
              <span>{b.believed}</span>
              <span className="text-muted">({age(now, b.as_of)})</span>
              {!b.up_to_date && <span className="text-muted">· really {b.actual}</span>}
            </li>
          ))}
        </ul>
      </Panel>

      {mind.lessons.length > 0 && (
        <Panel title="Lessons from past games" icon={<BookOpen size={16} />}>
          <ul className="space-y-2">
            {mind.lessons.map((l) => (
              <li key={l.id} className="rounded-lg border-2 border-amber/40 bg-[#fff4e6] p-2 text-xs leading-snug">
                <span className="mb-1 flex gap-1">
                  <Badge tone={l.status === "kept" ? "ok" : "amber"}>{l.status === "kept" ? "learned" : "trying it out"}</Badge>
                  {l.used && <Badge tone="teal">used in this game</Badge>}
                </span>
                “{l.text}”
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <Panel title="Recent memories" icon={<ScrollText size={16} />}>
        <ul className="space-y-1.5">
          {mind.memories.map((m, i) => <MemoryRow key={i} memory={m} nameOf={nameOf} />)}
        </ul>
      </Panel>
    </div>
  );
}

function ThinkingCard({ thinking, now }: { thinking: Thinking; now: number }) {
  const by = CHOSEN_BY[thinking.chosen_by];
  return (
    <div className="space-y-2 text-sm">
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge tone={by.tone}>{by.icon} {by.label}</Badge>
        <span className="text-xs text-muted">since {age(now, thinking.since)}</span>
      </div>
      {thinking.trigger && (
        <p className="text-xs"><span className="font-bold text-amber">Because:</span> {thinking.trigger}</p>
      )}
      {thinking.thought && (
        <p className="rounded-lg border border-[#c5b8f5] bg-[#f3f0ff] px-2 py-1 text-xs italic">“{thinking.thought}”</p>
      )}
      <p className="text-xs font-bold uppercase text-muted">Options it considered</p>
      <ol className="space-y-1">
        {thinking.options.map((o, i) => (
          <li key={o.strategy}
            className={`flex gap-2 rounded-lg border-2 px-2 py-1 text-xs leading-snug ${o.chosen ? "border-ink bg-[#fff3bf] font-semibold" : "border-line text-muted"}`}>
            <span className="shrink-0">{o.chosen ? <Check size={14} className="text-ok" /> : `${i + 1}.`}</span>
            <span>{o.summary}{i === 0 && !o.chosen && <span className="ml-1 font-normal">(the rules' first choice)</span>}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function BeliefRow({ fact, now }: { fact: BeliefFact; now: number }) {
  return (
    <li className={`rounded-lg border-2 px-2 py-1.5 text-xs leading-snug ${fact.up_to_date ? "border-line" : "border-amber/60 bg-[#fff9db]"}`}>
      <p className="flex items-center gap-1 font-bold">
        {fact.up_to_date ? <Check size={13} className="text-ok" /> : <TriangleAlert size={13} className="text-amber" />}
        {fact.subject}
        <span className="ml-auto font-normal text-muted">learned {age(now, fact.as_of)}</span>
      </p>
      {fact.up_to_date ? (
        <p className="text-muted">{fact.believed}</p>
      ) : (
        <p><span className="text-muted">Thinks:</span> <b className="text-danger">{fact.believed}</b> · <span className="text-muted">Really:</span> <b className="text-ok">{fact.actual}</b></p>
      )}
    </li>
  );
}

function MemoryRow({ memory, nameOf }: { memory: MindMemory; nameOf: (id: string) => string }) {
  const how = memory.source === "told" && memory.from_id ? `told by ${nameOf(memory.from_id)}`
    : memory.source === "signal" && memory.from_id ? `${nameOf(memory.from_id)}'s signal` : memory.source;
  return (
    <li className="flex gap-2 text-xs leading-snug">
      <span className="w-9 shrink-0 text-right font-mono text-muted">{memory.time}s</span>
      <span className="mt-px shrink-0 text-muted" title={how}>{MEMORY_ICON[memory.source] ?? <Eye size={13} />}</span>
      <span>{memory.text} <span className="text-muted">· {how}</span></span>
    </li>
  );
}
