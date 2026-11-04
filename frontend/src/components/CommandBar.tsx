import { Loader2, MessageCircle, Mic, MicOff, Radio, Send, Volume2, VolumeX, Wand2 } from "lucide-react";
import { useState } from "react";

import { useVoiceInput } from "../hooks/useSpeech";
import type { ActionResult, TwistsInfo } from "../types/api";
import { eventStyle } from "./eventStyle";
import { Button } from "./ui";

/** Do: orders the team obeys. Say: talk they hear but don't obey. Story: a twist the island makes happen. */
export type Channel = "do" | "say" | "story";

const EXAMPLES: Record<Channel, string[]> = {
  do: [
    "Kabir, pick up the timber and fix the bridge",
    "Meera, scout the forest and mark the traps",
    "Go to the temple and pull the lever",
    "Kabir, carry on with your own plan",
  ],
  say: [
    "How is everyone doing?",
    "Meera, what have you found?",
    "Be careful, the storm is getting closer!",
  ],
  story: [
    "A fallen tree blocks the Coast Road",
    "A gust of wind blows the timber to the bridge",
    "Lightning! The storm comes sooner",
  ],
};

const TABS: { id: Channel; label: string; icon: typeof Radio; hint: string }[] = [
  { id: "do", label: "Do", icon: Radio, hint: "Give orders. Teammates obey whatever they are able to do." },
  { id: "say", label: "Say", icon: MessageCircle, hint: "Talk by radio. Teammates hear and answer, but decide for themselves." },
  { id: "story", label: "Story", icon: Wand2, hint: "Write a twist. The island makes it happen, and everyone must adapt." },
];

const PLACEHOLDER: Record<Channel, string> = {
  do: "Tell your team what to do — e.g. “Kabir, fix the bridge. Meera, scout the forest.”",
  say: "Say something over the radio — e.g. “Meera, what have you found?”",
  story: "Write a twist — e.g. “A fallen tree blocks the Coast Road”",
};

const TONE_TEXT: Record<string, string> = {
  muted: "text-muted", amber: "text-amber", teal: "text-teal", danger: "text-danger", ok: "text-ok", sky: "text-sky",
};

/** Type or speak to the team (Do / Say), or co-write the story (Story). The server validates everything. */
export function CommandBar({
  disabled, pending, lastResult, sayResult = null, twistResult = null, twists, now = 0, voices, onVoices,
  onCommand, onSay, onTwist,
}: {
  disabled: boolean;
  pending: boolean;
  lastResult: ActionResult | null;
  sayResult?: ActionResult | null;
  twistResult?: ActionResult | null;
  twists?: TwistsInfo;
  now?: number;
  voices: boolean;
  onVoices: (on: boolean) => void;
  onCommand: (text: string) => void;
  onSay?: (text: string) => void;
  onTwist?: (text: string) => void;
}) {
  const [channel, setChannel] = useState<Channel>("do");
  const [text, setText] = useState("");
  const twistsLeft = twists ? twists.max - twists.used : 0;
  const cooldown = twists?.ready_at != null ? Math.max(0, Math.ceil(twists.ready_at - now)) : 0;
  const storyClosed = channel === "story" && (twistsLeft <= 0 || cooldown > 0);

  const send = (value: string) => {
    if (!value.trim() || disabled) return;
    const handler = channel === "say" ? onSay : channel === "story" ? onTwist : onCommand;
    handler?.(value.trim());
    setText("");
  };
  const voice = useVoiceInput(send);

  const result = channel === "say" ? sayResult : channel === "story" ? twistResult : lastResult;
  const lines = result?.events.filter((e) =>
    channel === "do" ? e.kind.startsWith("order_")
      : channel === "say" ? e.kind === "talked" && e.data.reply
        : e.kind === "story_twist") ?? [];
  const tabs = TABS.filter((t) => t.id === "do" || (t.id === "say" ? onSay : onTwist));
  const examples = channel === "story" && twists?.examples.length ? twists.examples.slice(0, 4) : EXAMPLES[channel];

  return (
    <section className="panel p-3" aria-label="Command your team">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
      {tabs.length > 1 && (
        <div className="flex shrink-0 flex-wrap items-center gap-1.5" role="tablist" aria-label="How to use the radio">
          {tabs.map((t) => {
            const Icon = t.icon;
            const active = channel === t.id;
            return (
              <button key={t.id} type="button" role="tab" aria-selected={active} title={t.hint}
                onClick={() => setChannel(t.id)}
                className={`flex items-center gap-1 rounded-full border-2 px-3 py-0.5 text-xs font-bold transition
                  ${active ? "border-ink bg-[#ffd43b] text-ink" : "border-ink/30 bg-white text-muted hover:border-ink"}`}>
                <Icon size={13} /> {t.label}
              </button>
            );
          })}
          <span className="ml-1 text-xs text-muted lg:hidden">{TABS.find((t) => t.id === channel)?.hint}</span>
        </div>
      )}

      <form className="flex min-w-0 flex-1 items-center gap-2" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        {(() => {
          const Icon = TABS.find((t) => t.id === channel)!.icon;
          return <Icon size={18} className={`shrink-0 ${channel === "story" ? "text-[#7048e8]" : "text-amber"}`} aria-hidden />;
        })()}
        <label htmlFor="command" className="sr-only">{channel === "do" ? "Command" : channel === "say" ? "Say" : "Story twist"}</label>
        <input
          id="command"
          value={voice.listening ? voice.interim || "Listening…" : text}
          onChange={(e) => setText(e.target.value)}
          maxLength={channel === "story" ? 200 : 280}
          disabled={disabled || voice.listening || storyClosed}
          placeholder={storyClosed ? (twistsLeft <= 0 ? "No twists left in this run." : `The island needs a moment… (${cooldown}s)`) : PLACEHOLDER[channel]}
          className="min-w-0 flex-1 rounded-xl border-[2.5px] border-ink bg-white px-3 py-2.5 text-sm font-semibold placeholder:font-medium placeholder:text-muted/80"
        />
        {voice.supported && (
          <Button
            variant={voice.listening ? "danger" : "ghost"}
            disabled={disabled || storyClosed}
            onClick={voice.listening ? voice.stop : voice.start}
            aria-label={voice.listening ? "Stop listening" : "Speak a command"}
            title="Speak (your browser transcribes the audio)"
          >
            {voice.listening ? <MicOff size={16} /> : <Mic size={16} />}
          </Button>
        )}
        <Button type="submit" variant="primary" disabled={disabled || pending || !text.trim() || storyClosed}
          aria-label={channel === "do" ? "Send command" : channel === "say" ? "Send message" : "Add twist"}>
          {pending ? <Loader2 size={16} className="animate-spin" /> : channel === "story" ? <Wand2 size={16} /> : <Send size={16} />}
        </Button>
        <Button onClick={() => onVoices(!voices)} aria-pressed={voices}
          aria-label={voices ? "Mute character voices" : "Read replies aloud"} title="Read replies aloud">
          {voices ? <Volume2 size={16} /> : <VolumeX size={16} />}
        </Button>
      </form>
      </div>

      {voice.error && <p role="alert" className="mt-2 text-xs text-danger">{voice.error}</p>}

      <div className="mt-2 min-h-5 space-y-0.5 text-sm" aria-live="polite">
        {channel === "story" && twists && (
          <p className="text-xs font-bold text-[#7048e8]">
            {twistsLeft} of {twists.max} twists left{cooldown > 0 && twistsLeft > 0 ? ` · next in ${cooldown}s` : ""}
          </p>
        )}
        {result && !result.ok && <p className="text-amber">✗ {result.message}</p>}
        {lines.map((e) => (
          <p key={e.seq} className={channel === "story" ? "flex items-center gap-1.5 font-semibold text-[#7048e8]" : TONE_TEXT[eventStyle(e).tone]}>
            {channel === "story" && <Wand2 size={14} className="shrink-0" aria-hidden />}
            {channel === "story" ? e.description.replace(/^Twist: /, "") : e.description}
          </p>
        ))}
        {channel === "story" && result?.ok && <p className="text-xs text-muted">{result.message}</p>}
        {!result && (
          <div className="scroll-thin flex gap-1.5 overflow-x-auto whitespace-nowrap pb-0.5 [@media(max-height:800px)]:lg:hidden">
            {examples.map((ex) => (
              <button key={ex} type="button" disabled={disabled || storyClosed} onClick={() => setText(ex)}
                className={`shrink-0 rounded-full border-2 px-2.5 py-0.5 text-xs font-semibold text-ink hover:border-ink
                  ${channel === "story" ? "border-[#b197fc]/60 bg-[#f3f0ff] hover:bg-[#e5dbff]" : "border-ink/30 bg-[#e7f5ff] hover:bg-[#d0ebff]"}`}>
                {ex}
              </button>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
