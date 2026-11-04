import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError, type PlayerAction, type RunSession } from "../services/api";
import type { ActionResult, StateView, WorldEvent } from "../types/api";

const POLL_MS = 600;
const MAX_EVENTS = 400;

export interface RunHandle {
  state: StateView | null;
  /** When `state` was received (ms since epoch), used to smooth animation between polls. */
  receivedAt: number;
  events: WorldEvent[];
  error: string | null;
  lost: boolean; // the run no longer exists or the token is invalid
  pending: boolean; // a player request is in flight
  act: (action: PlayerAction) => Promise<ActionResult | null>;
  talk: (targetId: string, message: string) => Promise<ActionResult | null>;
  command: (text: string) => Promise<ActionResult | null>;
  say: (text: string) => Promise<ActionResult | null>;
  twist: (text: string) => Promise<ActionResult | null>;
  advance: (ticks: number) => Promise<void>;
  pause: (paused: boolean) => Promise<void>;
}

/** Keeps a local mirror of one run by polling the backend. Never changes game state on its own. */
export function useRun(session: RunSession | null): RunHandle {
  const [state, setState] = useState<StateView | null>(null);
  const [receivedAt, setReceivedAt] = useState(0);
  const [events, setEvents] = useState<WorldEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lost, setLost] = useState(false);
  const [pending, setPending] = useState(false);
  const lastSeq = useRef(0);

  const handleError = useCallback((e: unknown) => {
    if (e instanceof ApiError && (e.status === 401 || e.status === 404)) setLost(true);
    setError(e instanceof Error ? e.message : String(e));
  }, []);

  const refresh = useCallback(async () => {
    if (!session) return;
    const next = await api.state(session);
    if (next.last_event_seq > lastSeq.current) {
      const fresh = await api.events(session, lastSeq.current);
      lastSeq.current = Math.max(lastSeq.current, fresh.last_event_seq);
      // Overlapping polls can fetch the same events; merging by sequence number keeps each one once.
      setEvents((prev) => {
        const newest = prev.length ? prev[prev.length - 1].seq : 0;
        return [...prev, ...fresh.events.filter((e) => e.seq > newest)].slice(-MAX_EVENTS);
      });
    }
    setState(next);
    setReceivedAt(Date.now());
    setError(null);
  }, [session]);

  useEffect(() => {
    lastSeq.current = 0;
    setEvents([]);
    setState(null);
    setLost(false);
    if (!session) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const loop = async () => {
      try {
        await refresh();
      } catch (e) {
        handleError(e);
      }
      if (!stopped) timer = setTimeout(loop, POLL_MS);
    };
    void loop();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [session, refresh, handleError]);

  const run = useCallback(
    async <T,>(fn: () => Promise<T>): Promise<T | null> => {
      if (!session) return null;
      setPending(true);
      try {
        const result = await fn();
        await refresh();
        return result;
      } catch (e) {
        handleError(e);
        return null;
      } finally {
        setPending(false);
      }
    },
    [session, refresh, handleError],
  );

  return {
    state,
    receivedAt,
    events,
    error,
    lost,
    pending,
    act: (action) => run(() => api.act(session!, action)),
    talk: (targetId, message) => run(() => api.talk(session!, targetId, message)),
    command: (text) => run(() => api.command(session!, text)),
    say: (text) => run(() => api.say(session!, text)),
    twist: (text) => run(() => api.twist(session!, text)),
    advance: async (ticks) => void (await run(() => api.advance(session!, ticks))),
    pause: async (paused) => void (await run(() => api.pause(session!, paused))),
  };
}
