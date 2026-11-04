import { Bot, Clock, Cpu, FastForward, Home, Pause, Play, RotateCcw } from "lucide-react";

import { formatClock } from "../game/geometry";
import type { Health, StateView } from "../types/api";
import { Badge, Button } from "./ui";

export function AiModeBadge({ health, mode }: { health: Health | null; mode?: "mock" | "live" }) {
  const live = (mode ?? health?.ai_mode) === "live";
  const providers = health?.llm_providers ?? [];
  return live ? (
    <Badge tone="teal" title={`Live LLMs, tried in order: ${providers.join(", ")}`}>
      <Cpu size={12} /> AI: live{providers[0] ? ` · ${providers[0].split(":")[0]}` : ""}
    </Badge>
  ) : (
    <Badge tone="muted" title="No LLM: a deterministic rule-based planner and template replies">
      <Bot size={12} /> AI: mock (rule-based)
    </Badge>
  );
}

export function TopBar({ state, health, simNow, pending, onPause, onSkip, onRestart, onMenu }: {
  state: StateView;
  health: Health | null;
  simNow: number;
  pending: boolean;
  onPause: (paused: boolean) => void;
  onSkip: () => void;
  onRestart: () => void;
  onMenu: () => void;
}) {
  const { run, clock } = state;
  const game = run.mode === "game";
  // The deadline is in simulated seconds; show the player the real time they have left.
  const remaining = clock.deadline !== null ? Math.ceil(Math.max(0, clock.deadline - simNow) / run.sim_speed) : null;
  const urgent = remaining !== null && remaining <= 60;
  return (
    <header className="flex flex-wrap items-center gap-3 border-b-[3px] border-ink bg-white px-4 py-2.5">
      <h1 className="font-display text-2xl font-bold text-[#ffd43b] glow-text">Off Script</h1>
      <Badge tone={game ? "amber" : "sky"}>{game ? "Game Mode" : "Default Mode"}</Badge>
      <span className="hidden sm:inline-flex"><AiModeBadge health={health} mode={run.ai_mode} /></span>
      {run.status === "running" && !game && <Badge tone="teal">The story runs on its own</Badge>}

      <div className="ml-auto flex flex-wrap items-center justify-end gap-2 sm:gap-3">
        <div className={`flex items-center gap-2 rounded-xl border-[2.5px] px-3 py-1 font-display text-xl font-bold tabular-nums
          ${urgent ? "animate-pulse border-danger bg-[#fff5f5] text-danger" : "border-ink bg-[#fff9db]"}`}
          title={game ? "Time until the storm (kept by the server)" : "Simulated time elapsed"}>
          <Clock size={16} />
          {remaining !== null ? formatClock(remaining) : formatClock(simNow)}
          <span className="text-xs text-muted">{game ? "until the storm" : "elapsed"}</span>
        </div>
        {!game && run.status === "running" && (
          <>
            <Button onClick={() => onPause(!run.paused)} disabled={pending} aria-label={run.paused ? "Resume" : "Pause"}>
              {run.paused ? <Play size={14} /> : <Pause size={14} />} {run.paused ? "Resume" : "Pause"}
            </Button>
            <Button onClick={onSkip} disabled={pending || run.paused} title="Skip 30 simulated seconds">
              <FastForward size={14} /> 30s
            </Button>
          </>
        )}
        <Button onClick={onRestart} disabled={pending} title="Start this mode again from the beginning" aria-label="Restart">
          <RotateCcw size={14} /> <span className="hidden sm:inline">Restart</span>
        </Button>
        <Button onClick={onMenu} aria-label="Main menu"><Home size={14} /></Button>
      </div>
    </header>
  );
}
