import { useCallback, useEffect, useRef, useState } from "react";

import type { WorldEvent } from "../types/api";

// Minimal typings for the Web Speech API (not in TypeScript's DOM library everywhere).
interface RecognitionResult {
  isFinal: boolean;
  0: { transcript: string };
}
interface RecognitionEvent {
  resultIndex: number;
  results: ArrayLike<RecognitionResult>;
}
interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: RecognitionEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}
type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | null {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/**
 * Voice input with the browser's built-in speech recognition (Chrome / Edge).
 * Note: these browsers send the audio to their vendor's speech service to transcribe it.
 */
export function useVoiceInput(onFinal: (text: string) => void) {
  const [supported] = useState(() => typeof window !== "undefined" && recognitionCtor() !== null);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<Recognition | null>(null);
  const onFinalRef = useRef(onFinal);
  onFinalRef.current = onFinal;

  const stop = useCallback(() => rec.current?.stop(), []);

  const start = useCallback(() => {
    const Ctor = recognitionCtor();
    if (!Ctor) return;
    setError(null);
    setInterim("");
    const r = new Ctor();
    r.lang = navigator.language || "en-US";
    r.interimResults = true;
    r.continuous = false;
    r.onresult = (e) => {
      let text = "";
      let final = false;
      for (let i = e.resultIndex; i < e.results.length; i++) {
        text += e.results[i][0].transcript;
        final ||= e.results[i].isFinal;
      }
      setInterim(text);
      if (final && text.trim()) onFinalRef.current(text.trim());
    };
    r.onerror = (e) =>
      setError(e.error === "not-allowed" ? "Microphone permission was denied." : `Voice input error: ${e.error}`);
    r.onend = () => {
      setListening(false);
      setInterim("");
    };
    rec.current = r;
    setListening(true);
    r.start();
  }, []);

  useEffect(() => () => rec.current?.stop(), []);
  return { supported, listening, interim, error, start, stop };
}

const VOICE_PITCH: Record<string, number> = { aria: 1.25, kabir: 0.8, meera: 1.05 };
const SPOKEN = new Set(["order_accepted", "order_refused", "order_failed", "order_completed", "talked", "help_accepted", "help_declined"]);

/** Reads characters' replies aloud with the browser's built-in speech synthesis (runs locally). */
export function useSpokenReplies(events: WorldEvent[], enabled: boolean, player: string | null) {
  const spoken = useRef(0);
  useEffect(() => {
    const newest = events.length ? events[events.length - 1].seq : 0;
    if (!enabled || typeof window === "undefined" || !("speechSynthesis" in window)) {
      spoken.current = newest; // don't replay a backlog when voices are switched on
      return;
    }
    for (const e of events) {
      if (e.seq <= spoken.current) continue;
      if (!SPOKEN.has(e.kind) || !e.actor || e.actor === player) continue;
      const line = new SpeechSynthesisUtterance(e.description.replace(/→/g, ", then"));
      line.pitch = VOICE_PITCH[e.actor] ?? 1;
      line.rate = 1.05;
      window.speechSynthesis.speak(line);
    }
    spoken.current = newest;
  }, [events, enabled, player]);
}
