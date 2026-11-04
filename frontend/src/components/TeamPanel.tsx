import { Bot, Footprints, Gem, Radio, User, Users } from "lucide-react";

import type { CharacterView, ObjectView } from "../types/api";
import { ToonAvatar } from "./ToonAvatar";
import { Badge, Panel, ProgressBar } from "./ui";

export function TeamPanel({ characters, objects, placeName, now, focus, onFocus }: {
  characters: CharacterView[];
  objects: ObjectView[];
  placeName: (id: string) => string;
  now: number;
  focus: string | null;
  onFocus: (id: string) => void;
}) {
  const itemName = (id: string) => objects.find((o) => o.id === id)?.name ?? id;
  return (
    <Panel title="The team" icon={<Users size={16} />}>
      <ul className="space-y-2">
        {characters.map((c) => {
          const where = c.travel
            ? `${placeName(c.travel.from_location)} → ${placeName(c.travel.to_location)}`
            : c.location_id ? placeName(c.location_id) : "—";
          const span = c.travel ? [c.travel.depart_at, c.travel.arrive_at] : c.activity ? [c.activity.started_at, c.activity.completes_at] : null;
          return (
            <li key={c.id}>
              <button onClick={() => onFocus(c.id)} aria-pressed={focus === c.id}
                className={`w-full rounded-lg border p-2.5 text-left transition ${focus === c.id ? "border-amber/70 bg-amber/5" : "border-line hover:border-line/80 hover:bg-panel-2/50"}`}>
                <div className="flex items-center gap-2">
                  <ToonAvatar id={c.id} color={c.color} size={32} />
                  <span className="font-semibold">{c.name}</span>
                  <span className="text-xs text-muted">{c.title}</span>
                  <span className="ml-auto">
                    {c.autonomous
                      ? <Badge tone="teal" title="Acts on its own goals and knowledge"><Bot size={12} /> autonomous</Badge>
                      : <Badge tone="amber"><User size={12} /> you</Badge>}
                  </span>
                </div>
                <p className="mt-1 flex items-center gap-1 text-xs text-muted">
                  <Footprints size={12} /> {where}
                  {c.activity && <span className="text-parchment/80"> · {c.activity.label}</span>}
                </p>
                {span && <div className="mt-1.5"><ProgressBar value={(now - span[0]) / Math.max(1, span[1] - span[0])} tone="teal" /></div>}
                {c.plan && (
                  <p className="mt-1.5 text-xs leading-snug">
                    <span className="text-muted">Goal:</span> {c.plan.goal}
                    <br />
                    <span className="text-muted">Plan:</span> {c.plan.summary}
                    {c.plan.status === "blocked" && <span className="ml-1 text-danger">(blocked)</span>}
                  </p>
                )}
                {(c.orders ?? []).length > 0 && (
                  <p className="mt-1 flex items-start gap-1 text-xs text-amber">
                    <Radio size={12} className="mt-0.5 shrink-0" /> Orders: {c.orders.join(" → ")}
                  </p>
                )}
                {c.inventory.length > 0 && (
                  <p className="mt-1 flex flex-wrap items-center gap-1 text-xs text-muted">
                    <Gem size={12} /> {c.inventory.map(itemName).join(", ")}
                  </p>
                )}
                {c.adaptations > 0 && <p className="mt-1 text-xs text-amber">Adapted {c.adaptations}× to changes</p>}
              </button>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
