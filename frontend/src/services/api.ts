import type {
  ActionResult, CharacterId, CreatedRun, EventsView, GameMode, Health, Journal, ProposedAction, RunAnalytics,
  RunSummary, StateView,
} from "../types/api";
import type { Scenario } from "../types/scenario";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export interface RunSession {
  runId: string;
  token: string;
}

const SESSION_KEY = "offscript.session";

/** The run id + token survive a page refresh (so a refresh resumes the same run and deadline). */
export function saveSession(session: RunSession | null): void {
  try {
    if (session) sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
    else sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // storage unavailable (private mode etc.): the game still works, it just can't resume after refresh
  }
}

export function loadSession(): RunSession | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as RunSession;
    return typeof parsed.runId === "string" && typeof parsed.token === "string" ? parsed : null;
  } catch {
    return null;
  }
}

function newRequestId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["X-Run-Token"] = token;
  const res = await fetch(`/api${path}`, { ...init, headers: { ...headers, ...(init.headers ?? {}) } });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      // keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

const post = (body: unknown) => ({ method: "POST", body: JSON.stringify(body ?? {}) });

/** Fields a player may send: the actor is always the run's player character, set by the server. */
export type PlayerAction = Omit<ProposedAction, "actor">;

export const api = {
  health: () => request<Health>("/health"),

  scenario: () => request<Scenario>("/scenario"),

  createRun: (mode: GameMode, player?: CharacterId) =>
    request<CreatedRun>("/runs", post(mode === "game" ? { mode, player_character: player } : { mode })),

  start: (s: RunSession) => request<StateView>(`/runs/${s.runId}/start`, post({}), s.token),

  state: (s: RunSession) => request<StateView>(`/runs/${s.runId}/state`, {}, s.token),

  events: (s: RunSession, after: number) =>
    request<EventsView>(`/runs/${s.runId}/events?after=${after}&limit=500`, {}, s.token),

  act: (s: RunSession, action: PlayerAction) => {
    // Strip nulls and the actor: the backend forbids unknown or player-chosen fields.
    const body: Record<string, unknown> = { request_id: newRequestId() };
    for (const [k, v] of Object.entries(action)) if (v !== null && v !== undefined && k !== "actor") body[k] = v;
    return request<ActionResult>(`/runs/${s.runId}/actions`, post(body), s.token);
  },

  talk: (s: RunSession, targetId: string, message: string) =>
    request<ActionResult>(`/runs/${s.runId}/dialogue`,
      post({ target_id: targetId, message, request_id: newRequestId() }), s.token),

  command: (s: RunSession, text: string) =>
    request<ActionResult>(`/runs/${s.runId}/command`, post({ text, request_id: newRequestId() }), s.token),

  say: (s: RunSession, text: string) =>
    request<ActionResult>(`/runs/${s.runId}/say`, post({ text, request_id: newRequestId() }), s.token),

  twist: (s: RunSession, text: string) =>
    request<ActionResult>(`/runs/${s.runId}/twist`, post({ text, request_id: newRequestId() }), s.token),

  advance: (s: RunSession, ticks: number) => request<StateView>(`/runs/${s.runId}/advance`, post({ ticks }), s.token),

  pause: (s: RunSession, paused: boolean) => request<StateView>(`/runs/${s.runId}/pause`, post({ paused }), s.token),

  restart: (s: RunSession) => request<CreatedRun>(`/runs/${s.runId}/restart`, post({}), s.token),

  analytics: (s: RunSession) => request<RunAnalytics>(`/runs/${s.runId}/analytics`, {}, s.token),

  finishedRuns: () => request<RunSummary[]>("/runs?status=finished&limit=100"),

  journal: () => request<Journal>("/journal"),

  resetJournal: () => request<Journal>("/journal/reset", post({})),
};
