import { ArrowLeft, ArrowRight, Clock, Gamepad2, MessageCircle, MousePointerClick, Radio, Wand2 } from "lucide-react";
import { useState } from "react";

import type { CharacterId } from "../types/api";
import type { Scenario } from "../types/scenario";
import { ToonAvatar } from "./ToonAvatar";
import { Button } from "./ui";

const BRIEFED_KEY = "offscript.briefed";

export function hasBeenBriefed(): boolean {
  try {
    return localStorage.getItem(BRIEFED_KEY) === "yes";
  } catch {
    return false;
  }
}

function markBriefed(): void {
  try {
    localStorage.setItem(BRIEFED_KEY, "yes");
  } catch {
    // per-browser convenience only
  }
}

/** A tiny drawn lighthouse, matching the one on the map. */
function LighthouseIcon({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 48" aria-hidden>
      <path d="M12 44 L28 44 L25 14 L15 14 Z" fill="#fff" stroke="#1d2142" strokeWidth="2.5" strokeLinejoin="round" />
      <path d="M13.2 36 L26.8 36 L26.2 30 L13.8 30 Z M14.6 24 L25.4 24 L25 19 L15 19 Z" fill="#e03131" />
      <rect x="14" y="6" width="12" height="8" rx="1.5" fill="#ffe066" stroke="#1d2142" strokeWidth="2.5" />
      <path d="M12 6 L28 6 L20 0 Z" fill="#e03131" stroke="#1d2142" strokeWidth="2.5" strokeLinejoin="round" />
    </svg>
  );
}

function CrystalIcon({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 34 34" aria-hidden>
      <circle cx="17" cy="17" r="16" fill="#fff3bf" />
      <path d="M17 4 L20.5 13 L30 13.5 L22.5 19.5 L25 29 L17 23.5 L9 29 L11.5 19.5 L4 13.5 L13.5 13 Z"
        fill="#ffe066" stroke="#1d2142" strokeWidth="2.2" strokeLinejoin="round" />
    </svg>
  );
}

const WAYS = [
  { icon: Radio, tab: "Do", text: "Give orders", example: "Kabir, fix the bridge" },
  { icon: MessageCircle, tab: "Say", text: "Chat by radio", example: "Meera, what did you find?" },
  { icon: Wand2, tab: "Story", text: "Write a twist", example: "A tree blocks the Coast Road" },
];

function Step1() {
  return (
    <>
      <div className="flex items-center justify-center gap-3 py-2">
        <div className="text-center"><CrystalIcon size={44} /><p className="mt-1 text-xs font-bold">Sun Crystal</p></div>
        <svg width="90" height="14" viewBox="0 0 90 14" aria-hidden>
          <path d="M2 7 H80" stroke="#1d2142" strokeWidth="3" strokeDasharray="7 6" strokeLinecap="round" />
          <path d="M78 1 L88 7 L78 13 Z" fill="#1d2142" />
        </svg>
        <div className="text-center"><LighthouseIcon size={44} /><p className="mt-1 text-xs font-bold">Lighthouse</p></div>
      </div>
      <h2 className="font-display text-2xl">Bring the light home</h2>
      <p className="mt-2 text-muted">
        Carry the <b className="text-ink">Sun Crystal</b> from the Flooded Chamber to the <b className="text-ink">Lighthouse</b> and
        light the beacon.
      </p>
      <p className="mt-2 inline-flex items-center gap-1.5 rounded-full border-2 border-danger bg-[#fff5f5] px-3 py-1 text-sm font-bold text-danger">
        <Clock size={14} /> The storm arrives in 5 minutes
      </p>
    </>
  );
}

function Step2({ scenario, player }: { scenario: Scenario | null; player: CharacterId | null }) {
  const chars = scenario?.characters ?? [];
  const me = chars.find((c) => c.id === player);
  return (
    <>
      <div className="flex items-end justify-center gap-4 py-2">
        {chars.map((c) => (
          <div key={c.id} className="text-center">
            <ToonAvatar id={c.id} color={c.color} size={c.id === player ? 64 : 52} />
            <p className={`mt-1 text-xs font-bold ${c.id === player ? "rounded-full bg-[#ffd43b] px-2" : ""}`}>
              {c.id === player ? "You" : c.name}
            </p>
          </div>
        ))}
      </div>
      <h2 className="font-display text-2xl">Your team thinks for itself</h2>
      <p className="mt-2 text-muted">
        {me ? <>You are <b className="text-ink">{me.name}</b>. </> : null}
        Your friends make their own plans and change them when things go wrong. They only know what they have
        seen or been told, so keep them posted.
      </p>
    </>
  );
}

function Step3() {
  return (
    <>
      <ul className="grid gap-2 py-2 sm:grid-cols-3">
        {WAYS.map(({ icon: Icon, tab, text, example }) => (
          <li key={tab} className="rounded-xl border-[2.5px] border-ink bg-[#f8fbff] p-2.5 text-left">
            <span className="inline-flex items-center gap-1 rounded-full border-2 border-ink bg-[#ffd43b] px-2 text-xs font-bold">
              <Icon size={12} /> {tab}
            </span>
            <p className="mt-1.5 text-sm font-bold">{text}</p>
            <p className="text-xs text-muted">“{example}”</p>
          </li>
        ))}
      </ul>
      <h2 className="font-display text-2xl">Talk, act, or twist the story</h2>
      <p className="mt-2 text-muted">
        Type or speak in the radio bar under the map. You can also walk and work yourself: tap an action
        in the <b className="text-ink">You</b> tab. Every action takes island time.
      </p>
    </>
  );
}

/** The three-step briefing before a Game Mode run starts (the storm clock is not running yet). */
export function Briefing({ scenario, player, busy, onStart, onBack }: {
  scenario: Scenario | null;
  player: CharacterId;
  busy: boolean;
  onStart: () => void;
  onBack: () => void;
}) {
  const [step, setStep] = useState(0);
  const steps = [<Step1 key="1" />, <Step2 key="2" scenario={scenario} player={player} />, <Step3 key="3" />];
  const last = step === steps.length - 1;
  const start = () => {
    markBriefed();
    onStart();
  };
  return (
    <div className="mx-auto flex min-h-dvh max-w-xl flex-col justify-center px-4 py-10">
      <section className="panel animate-rise p-6 text-center sm:p-8" aria-label="How to play" aria-live="polite">
        <p className="mb-3 text-xs font-bold text-muted">How to play · {step + 1} of {steps.length}</p>
        <div key={step} className="animate-rise">{steps[step]}</div>
        <div className="mt-6 flex items-center justify-between gap-2">
          {step === 0
            ? <Button onClick={onBack}><ArrowLeft size={14} /> Back</Button>
            : <Button onClick={() => setStep(step - 1)}><ArrowLeft size={14} /> Previous</Button>}
          <div className="flex gap-1.5" aria-hidden>
            {steps.map((_, i) => (
              <span key={i} className={`size-2.5 rounded-full border-2 border-ink ${i === step ? "bg-[#ffd43b]" : "bg-white"}`} />
            ))}
          </div>
          {last ? (
            <Button variant="primary" onClick={start} disabled={busy}><Gamepad2 size={16} /> Start the adventure</Button>
          ) : (
            <Button variant="primary" onClick={() => setStep(step + 1)}>Next <ArrowRight size={14} /></Button>
          )}
        </div>
        {!last && (
          <button type="button" onClick={start} disabled={busy}
            className="mt-4 text-xs font-bold text-muted underline underline-offset-4 hover:text-ink">
            Skip and start now
          </button>
        )}
      </section>
    </div>
  );
}

/** The same guide, compact, for the in-game Guide tab. */
export function GuideCompact({ game }: { game: boolean }) {
  return (
    <div className="space-y-4 text-sm">
      <section>
        <h3 className="flex items-center gap-2 font-display text-base"><CrystalIcon size={22} /> The goal</h3>
        <p className="mt-1 text-muted">
          Carry the Sun Crystal from the Flooded Chamber to the Lighthouse and light the beacon
          {game ? " before the storm wall (the dark clouds on the right) reaches the island." : "."}
        </p>
      </section>
      <section>
        <h3 className="font-display text-base">How the team works</h3>
        <p className="mt-1 text-muted">
          Characters plan on their own and only know what they've seen or been told. The <b className="text-ink">Team</b> tab
          shows what each one is trying to do.
        </p>
      </section>
      {game && (
        <section>
          <h3 className="font-display text-base">Three ways to play</h3>
          <ul className="mt-1 space-y-1.5">
            {WAYS.map(({ icon: Icon, tab, text, example }) => (
              <li key={tab} className="flex items-start gap-2">
                <span className="inline-flex shrink-0 items-center gap-1 rounded-full border-2 border-ink bg-[#ffd43b] px-2 text-xs font-bold">
                  <Icon size={12} /> {tab}
                </span>
                <span className="text-muted"><b className="text-ink">{text}</b>, e.g. “{example}”</span>
              </li>
            ))}
            <li className="flex items-start gap-2">
              <span className="inline-flex shrink-0 items-center gap-1 rounded-full border-2 border-ink bg-white px-2 text-xs font-bold">
                <MousePointerClick size={12} /> You
              </span>
              <span className="text-muted"><b className="text-ink">Act yourself</b>: tap an action. Each one takes island time.</span>
            </li>
          </ul>
        </section>
      )}
      <section>
        <h3 className="font-display text-base">Reading the map</h3>
        <p className="mt-1 text-muted">
          Red dashes are broken, dashed lines need a special skill, and a padlock means locked. The
          <b className="text-ink"> Storybook</b> retells everything as it happens.
        </p>
      </section>
    </div>
  );
}
