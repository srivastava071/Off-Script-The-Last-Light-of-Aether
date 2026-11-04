import { Eye, Gamepad2, Play } from "lucide-react";

import { ToonAvatar } from "../components/ToonAvatar";
import { AiModeBadge } from "../components/TopBar";
import { Badge, Button, Panel } from "../components/ui";
import type { Health } from "../types/api";
import { prettyAbility, type Scenario } from "../types/scenario";

/** A little drawn island with the three heroes standing on it, for the title screen. */
function HeroIsland({ scenario }: { scenario: Scenario | null }) {
  const chars = scenario?.characters ?? [];
  return (
    <div className="relative mx-auto mt-6 w-full max-w-[560px]" aria-hidden>
      <svg viewBox="0 0 560 210" className="w-full">
        <ellipse cx="280" cy="168" rx="268" ry="36" fill="#45bdee" />
        <ellipse cx="280" cy="162" rx="246" ry="30" fill="#a5ecff" opacity="0.7" />
        <path d="M60 158 C 90 110, 190 96, 280 98 C 380 96, 480 112, 500 158 C 430 182, 140 184, 60 158 Z"
          fill="#ffe3a3" stroke="#1d2142" strokeWidth="4" strokeLinejoin="round" />
        <path d="M92 150 C 120 116, 200 106, 280 108 C 370 106, 450 118, 470 150 C 400 168, 160 170, 92 150 Z" fill="#86d465" />
        {/* lighthouse */}
        <g transform="translate(102 64)">
          <path d="M8 84 L36 84 L31 22 L13 22 Z" fill="#fff" stroke="#1d2142" strokeWidth="3" strokeLinejoin="round" />
          <path d="M9.6 66 L34.4 66 L33.6 56 L10.4 56 Z M11.4 44 L32.6 44 L32 36 L12 36 Z" fill="#e03131" />
          <rect x="11" y="8" width="22" height="14" rx="2" fill="#ffe066" stroke="#1d2142" strokeWidth="3" />
          <path d="M8 8 L36 8 L22 -6 Z" fill="#e03131" stroke="#1d2142" strokeWidth="3" strokeLinejoin="round" />
          <path d="M33 14 L120 -14 L120 34 Z" fill="#ffe066" className="animate-[beam_3s_ease-in-out_infinite]" />
        </g>
        {/* temple */}
        <g transform="translate(398 86)">
          <rect x="0" y="44" width="76" height="14" rx="2" fill="#cbb894" stroke="#1d2142" strokeWidth="3" />
          <rect x="10" y="22" width="56" height="24" rx="2" fill="#e8dcc2" stroke="#1d2142" strokeWidth="3" />
          <path d="M4 22 L72 22 L38 2 Z" fill="#e0a800" stroke="#1d2142" strokeWidth="3" strokeLinejoin="round" />
          <path d="M29 46 L29 32 A9 9 0 0 1 47 32 L47 46 Z" fill="#5c4033" stroke="#1d2142" strokeWidth="2.5" />
        </g>
        {/* palm */}
        <path d="M470 150 Q 478 120 492 100" stroke="#1d2142" strokeWidth="9" fill="none" strokeLinecap="round" />
        <path d="M470 150 Q 478 120 492 100" stroke="#b07a4a" strokeWidth="5" fill="none" strokeLinecap="round" />
        <path d="M492 100 q -30 -6 -40 10 q 22 -14 40 -10 q 4 -26 30 -26 q -26 8 -30 26 q 26 -4 34 16 q -16 -16 -34 -16 Z"
          fill="#51cf66" stroke="#1d2142" strokeWidth="2.5" strokeLinejoin="round" />
        {/* crystal */}
        <g transform="translate(280 40)">
          <g className="animate-[float_2.4s_ease-in-out_infinite]">
            <circle r="22" fill="#ffe066" opacity="0.35" />
            <path d="M0 -15 L4 -5 L15 -4.5 L6.5 2.5 L9.5 13.5 L0 7.5 L-9.5 13.5 L-6.5 2.5 L-15 -4.5 L-4 -5 Z"
              fill="#ffe066" stroke="#1d2142" strokeWidth="2.5" strokeLinejoin="round" />
          </g>
        </g>
      </svg>
      <div className="absolute inset-x-0 bottom-[22%] flex origin-bottom scale-[0.7] items-end justify-center gap-3 sm:scale-100">
        {chars.map((c, i) => (
          <div key={c.id} className="animate-[float_2.4s_ease-in-out_infinite]" style={{ animationDelay: `${i * 0.25}s` }}>
            <ToonAvatar id={c.id} color={c.color} size={i === 1 ? 70 : 60} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function MainMenu({ scenario, health, canResume, busy, error, onDefault, onGame, onResume }: {
  scenario: Scenario | null;
  health: Health | null;
  canResume: boolean;
  busy: boolean;
  error: string | null;
  onDefault: () => void;
  onGame: () => void;
  onResume: () => void;
}) {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:py-12">
      <section className="text-center">
        <h1 className="font-display text-5xl font-bold text-[#ffd43b] glow-text sm:text-7xl">
          <span className="animate-wobble">Off Script</span>
          <span className="mt-3 block text-2xl text-white glow-text sm:text-4xl">The Last Light of Aether</span>
        </h1>
        <HeroIsland scenario={scenario} />
        <p className="mx-auto mt-4 max-w-xl text-lg leading-relaxed text-ink">
          A storm is coming and Aether's barrier is failing. Three friends must bring the Sun Crystal home,
          and <b>they think for themselves</b>.
        </p>

        <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row sm:items-start">
          {canResume && (
            <div className="flex flex-col items-center gap-1">
              <Button variant="primary" onClick={onResume} disabled={busy} className="w-64 !py-3 text-base">
                <Play size={18} /> Resume your run
              </Button>
              <span className="text-xs text-muted">Pick up where you left off</span>
            </div>
          )}
          <div className="flex flex-col items-center gap-1">
            <Button variant={canResume ? "ghost" : "primary"} onClick={onGame} disabled={busy} className="w-64 !py-3 text-base">
              <Gamepad2 size={18} /> Play
            </Button>
            <span className="text-xs text-muted">Be one hero · 5-minute storm</span>
          </div>
          <div className="flex flex-col items-center gap-1">
            <Button variant="ghost" onClick={onDefault} disabled={busy} className="w-64 !py-3 text-base">
              <Eye size={18} /> Watch the AI play
            </Button>
            <span className="text-xs text-muted">Sit back: the team solves it alone</span>
          </div>
        </div>
        {error && <p role="alert" className="mt-4 text-sm text-danger">{error}</p>}
        <div className="mt-4 flex justify-center"><AiModeBadge health={health} /></div>
      </section>

      <h2 className="mt-12 text-center font-display text-2xl text-ink">Meet the team</h2>
      <div className="mt-4 grid gap-4 md:grid-cols-3">
        {(scenario?.characters ?? []).map((c) => (
          <Panel key={c.id} className="animate-rise">
            <div className="flex items-center gap-3">
              <ToonAvatar id={c.id} color={c.color} size={56} />
              <div>
                <h3 className="font-display text-lg">{c.name}</h3>
                <p className="text-xs text-muted">{c.title}</p>
              </div>
            </div>
            <p className="mt-3 text-sm text-muted">{c.personality}</p>
            <div className="mt-3 flex flex-wrap gap-1">
              {c.abilities.map((a) => <Badge key={a} tone="amber">{prettyAbility(a)}</Badge>)}
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}
