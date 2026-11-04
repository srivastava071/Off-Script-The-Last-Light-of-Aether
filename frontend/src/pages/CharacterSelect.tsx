import { ArrowLeft, Check, Gauge, Package, ShieldAlert, Sparkles, Target } from "lucide-react";
import { useState } from "react";

import { ToonAvatar } from "../components/ToonAvatar";
import { Badge, Button } from "../components/ui";
import type { CharacterId } from "../types/api";
import { prettyAbility, type Scenario } from "../types/scenario";

export function CharacterSelect({ scenario, busy, error, onBack, onSelect }: {
  scenario: Scenario | null;
  busy: boolean;
  error: string | null;
  onBack: () => void;
  onSelect: (id: CharacterId) => void;
}) {
  const [chosen, setChosen] = useState<CharacterId | null>(null);
  const characters = scenario?.characters ?? [];
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <Button onClick={onBack}><ArrowLeft size={14} /> Back</Button>
      <h1 className="mt-6 text-center font-display text-4xl font-bold text-white glow-text sm:text-5xl">Choose your character</h1>
      <p className="mt-2 text-center text-muted">You control one. The other two will act on their own.</p>

      <div className="mt-8 grid gap-4 md:grid-cols-3" role="radiogroup" aria-label="Characters">
        {characters.map((c) => {
          const selected = chosen === c.id;
          return (
            <button key={c.id} role="radio" aria-checked={selected} onClick={() => setChosen(c.id)}
              className={`panel group p-5 text-left transition ${selected ? "-translate-y-1 !bg-panel-2 ring-4 ring-[#ffd43b]" : "hover:-translate-y-1"}`}>
              <div className="flex items-center gap-3">
                <ToonAvatar id={c.id} color={c.color} size={72} />
                <div>
                  <h2 className="font-display text-2xl">{c.name}</h2>
                  <p className="text-sm text-amber">{c.title}</p>
                </div>
                {selected && <Check className="ml-auto text-amber" aria-hidden />}
              </div>
              <p className="mt-4 text-sm text-muted">{c.personality}</p>
              <p className="mt-3 flex gap-2 text-sm"><Target size={16} className="mt-0.5 shrink-0 text-amber" />{c.primary_goal}</p>
              <h3 className="mt-4 flex items-center gap-1 text-xs font-semibold uppercase text-muted"><Sparkles size={12} /> Abilities</h3>
              <div className="mt-1 flex flex-wrap gap-1">
                {c.abilities.map((a) => <Badge key={a} tone="amber">{prettyAbility(a)}</Badge>)}
              </div>
              <h3 className="mt-3 flex items-center gap-1 text-xs font-semibold uppercase text-muted"><ShieldAlert size={12} /> Limitations</h3>
              <ul className="mt-1 space-y-0.5 text-xs text-muted">
                {c.restrictions.map((r) => <li key={r}>• {r}</li>)}
              </ul>
              <p className="mt-3 flex flex-wrap gap-3 text-xs text-muted">
                <span className="flex items-center gap-1"><Gauge size={12} /> speed ×{c.speed_multiplier}</span>
                <span className="flex items-center gap-1"><Package size={12} /> carries {c.carry_capacity}{c.can_carry_heavy ? "" : ", nothing heavy"}</span>
              </p>
            </button>
          );
        })}
      </div>

      <div className="mt-8 flex flex-col items-center gap-2">
        <Button variant="primary" className="w-72 !py-3 text-base" disabled={!chosen || busy}
          onClick={() => chosen && onSelect(chosen)}>
          {chosen ? `Play as ${characters.find((c) => c.id === chosen)?.name}` : "Select a character"}
        </Button>
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      </div>
    </div>
  );
}
