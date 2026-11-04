import { ChevronRight, Hourglass, Loader2, Swords } from "lucide-react";

import type { PlayerAction } from "../services/api";
import type { ActionOption, ActionResult, CharacterView } from "../types/api";
import { Button, Panel, ProgressBar } from "./ui";

const GROUPS: { title: string; types: string[] }[] = [
  { title: "Travel", types: ["move"] },
  { title: "Skills & mechanisms", types: [
    "repair_bridge", "clear_route", "block_route", "discover_route", "detect_traps", "repair_mechanism",
    "decode_symbols", "pull_lever", "repair_lighthouse", "install_crystal", "activate_lighthouse", "signal",
  ] },
  { title: "Items", types: ["pick_up", "drop", "give"] },
  { title: "Team", types: ["ask", "request_help"] },
  { title: "Other", types: ["inspect", "wait"] },
];

/** Less common groups start folded, so the first view is short. */
const COLLAPSED = new Set(["Team", "Other"]);

export function groupActions(options: ActionOption[]): { title: string; options: ActionOption[] }[] {
  // Talking has its own panel; everything else the backend offered is grouped here.
  const usable = options.filter((o) => o.action.type !== "talk");
  return GROUPS.map((g) => ({ title: g.title, options: usable.filter((o) => g.types.includes(o.action.type)) }))
    .filter((g) => g.options.length > 0);
}

export function ActionPanel({ me, options, now, pending, lastResult, onAct, placeName = (id) => id }: {
  me: CharacterView;
  placeName?: (id: string) => string;
  options: ActionOption[];
  now: number;
  pending: boolean;
  lastResult: ActionResult | null;
  onAct: (action: PlayerAction) => void;
}) {
  const busy = me.travel ?? me.activity;
  const groups = groupActions(options);

  return (
    <Panel title="Your actions" icon={<Swords size={16} />}>
      {busy ? (
        <BusyState me={me} now={now} placeName={placeName} />
      ) : groups.length === 0 ? (
        <p className="text-sm text-muted">No actions available right now.</p>
      ) : (
        <div className="space-y-3">
          {groups.map((g) => (
            <details key={g.title} open={!COLLAPSED.has(g.title)} className="group">
              <summary className="mb-1.5 flex cursor-pointer list-none items-center gap-1 text-xs font-bold uppercase tracking-wide text-muted hover:text-ink">
                <ChevronRight size={13} className="transition-transform group-open:rotate-90" aria-hidden />
                {g.title} <span className="font-semibold normal-case tracking-normal">({g.options.length})</span>
              </summary>
              <div className="flex flex-wrap gap-1.5">
                {g.options.map((o) => (
                  <Button
                    key={o.label}
                    variant={o.available ? "subtle" : "ghost"}
                    disabled={!o.available || pending}
                    title={o.reason ?? `${o.label} (${o.seconds}s)`}
                    onClick={() => onAct(o.action)}
                    className="!px-2.5 !py-1.5 text-left"
                  >
                    <span>{o.label}</span>
                    {o.available && <span className="text-xs text-muted">{o.seconds}s</span>}
                  </Button>
                ))}
              </div>
              {g.options.filter((o) => !o.available && o.reason).map((o) => (
                <p key={`${o.label}-why`} className="mt-1 text-xs text-muted">
                  <span className="text-parchment/80">{o.label}:</span> {o.reason}
                </p>
              ))}
            </details>
          ))}
        </div>
      )}

      <div className="mt-3 min-h-6 text-sm" aria-live="polite">
        {pending && (
          <span className="inline-flex items-center gap-2 text-muted">
            <Loader2 size={14} className="animate-spin" /> Sending to the island…
          </span>
        )}
        {!pending && lastResult && (
          <p className={lastResult.ok ? "text-ok" : "text-amber"}>
            {lastResult.ok ? "✓ " : "✗ "}
            {lastResult.message}
          </p>
        )}
      </div>
    </Panel>
  );
}

function BusyState({ me, now, placeName }: { me: CharacterView; now: number; placeName: (id: string) => string }) {
  const start = me.travel?.depart_at ?? me.activity!.started_at;
  const end = me.travel?.arrive_at ?? me.activity!.completes_at;
  const what = me.travel ? `Travelling to the ${placeName(me.travel.to_location)}` : `Busy: ${me.activity!.label}`;
  return (
    <div className="space-y-2">
      <p className="flex items-center gap-2 text-sm">
        <Hourglass size={14} className="text-amber" /> {what}
      </p>
      <ProgressBar value={(now - start) / Math.max(1, end - start)} label={what} />
      <p className="text-xs text-muted">Actions unlock in about {Math.max(0, Math.ceil(end - now))}s of island time.</p>
    </div>
  );
}
