import { Construction, Lock, Maximize2, Minimize2, Smartphone, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { bubbleFor } from "../game/bubbles";
import { IslandMap, type MindOverlay } from "../game/IslandScene";
import type { StateView, WorldEvent } from "../types/api";
import { PULSE } from "./eventStyle";

/** Hosts the Phaser island. It only renders what the backend state says. */
export function MapView({ state, receivedAt, events, focus, onFocus, mind = null, className = "" }: {
  className?: string;
  state: StateView;
  receivedAt: number;
  events: WorldEvent[];
  focus: string | null;
  onFocus: (id: string) => void;
  mind?: MindOverlay | null;
}) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<IslandMap | null>(null);
  const onFocusRef = useRef(onFocus);
  const pulsedSeq = useRef(0);
  const [big, setBig] = useState(false);
  onFocusRef.current = onFocus;

  useEffect(() => {
    // Re-fit the canvas once the new layout has settled, and close full screen with Escape.
    const timers = [0, 120, 400].map((ms) => setTimeout(() => map.current?.refresh(), ms));
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setBig(false);
    if (big) window.addEventListener("keydown", onKey);
    return () => {
      timers.forEach(clearTimeout);
      window.removeEventListener("keydown", onKey);
    };
  }, [big]);

  useEffect(() => {
    if (!host.current) return;
    map.current = new IslandMap(host.current, (id) => onFocusRef.current(id));
    // The map fills a resizable area; re-fit the canvas whenever that area changes size.
    const watcher = new ResizeObserver(() => map.current?.refresh());
    watcher.observe(host.current);
    return () => {
      watcher.disconnect();
      map.current?.destroy();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    map.current?.setFrame({ state, receivedAt, focus, mind });
  }, [state, receivedAt, focus, mind]);

  useEffect(() => {
    // Pulse the map where important things just happened (only events newer than the last pulse).
    const fresh = events.filter((e) => e.seq > pulsedSeq.current);
    if (fresh.length === 0) return;
    const first = pulsedSeq.current === 0;
    pulsedSeq.current = fresh[fresh.length - 1].seq;
    if (first) return; // don't replay history when (re)joining a run
    for (const e of fresh) {
      const color = PULSE[e.kind];
      const loc = state.locations.find((l) => l.id === e.location_id);
      if (color && loc) map.current?.pulse(loc, color);
      const bubble = bubbleFor(e);
      if (bubble) map.current?.say(bubble);
    }
  }, [events, state.locations]);

  return (
    <div className={big ? "fixed inset-0 z-40 flex flex-col items-center justify-center gap-3 bg-[#1d2142]/85 p-2 sm:p-4" : `flex flex-col ${className}`}
      onClick={big ? (e) => e.target === e.currentTarget && setBig(false) : undefined}>
    <div className={`panel relative overflow-hidden p-0 ${big ? "w-[min(100%,calc((100dvh-3rem)*10/7))]" : "lg:min-h-0 lg:flex-1"}`}>
      {/* The sea gradient behind the canvas matches the painted sea, so any spare room reads as more ocean. */}
      <div ref={host} aria-label="Map of Aether Island" role="img"
        className={`w-full bg-[linear-gradient(180deg,#74daf8_0%,#45bdee_55%,#2a98d6_100%)] ${big ? "aspect-[10/7]" : "aspect-[10/7] lg:aspect-auto lg:h-full"}`} />
      <button type="button" onClick={() => setBig(!big)} aria-label={big ? "Exit full-screen map" : "Full-screen map"}
        title={big ? "Exit full screen (Esc)" : "Full-screen map"}
        className="absolute right-2 top-2 grid size-9 place-items-center rounded-xl border-[2.5px] border-ink bg-white shadow-[0_3px_0_#1d2142] hover:bg-[#fff3bf] active:translate-y-0.5 active:shadow-none">
        {big ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
      </button>
      <ul aria-label="Map key"
        className="pointer-events-none absolute bottom-2 left-2 hidden items-center gap-3 rounded-full border-2 border-ink bg-white/95 px-3 py-1 text-[11px] font-bold text-ink sm:flex">
        <li className="flex items-center gap-1.5"><Swatch color="#f7dfa8" /> trail</li>
        <li className="flex items-center gap-1.5"><Swatch color="#ff6b6b" dashed /> broken</li>
        <li className="flex items-center gap-1.5"><Construction size={13} className="text-[#9c6644]" /> blocked</li>
        <li className="flex items-center gap-1.5"><Lock size={13} className="text-[#b08968]" /> locked</li>
        <li className="flex items-center gap-1.5"><TriangleAlert size={13} className="text-[#e8a400]" /> traps</li>
        <li className="flex items-center gap-1.5"><span className="rounded-full border-2 border-ink bg-[#ffd43b] px-1.5 text-[9px] leading-3">YOU</span> you</li>
      </ul>
    </div>
    {big && (
      <p className="flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-bold text-ink portrait:flex landscape:hidden">
        <Smartphone size={14} className="rotate-90" aria-hidden /> Turn your phone sideways for a bigger map
      </p>
    )}
    </div>
  );
}

function Swatch({ color, dashed = false }: { color: string; dashed?: boolean }) {
  return (
    <svg width="22" height="8" viewBox="0 0 22 8" aria-hidden>
      <line x1="2" y1="4" x2="20" y2="4" stroke="#1d2142" strokeWidth="7" strokeLinecap="round" strokeDasharray={dashed ? "5 4" : undefined} />
      <line x1="2" y1="4" x2="20" y2="4" stroke={color} strokeWidth="4" strokeLinecap="round" strokeDasharray={dashed ? "5 4" : undefined} />
    </svg>
  );
}
