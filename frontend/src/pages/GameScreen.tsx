import { BarChart3, BookOpen, CircleHelp, Flag, Loader2, Package, ScrollText, User, Users } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { ActionPanel } from "../components/ActionPanel";
import { CommandBar } from "../components/CommandBar";
import { DialoguePanel } from "../components/DialoguePanel";
import { EventTimeline } from "../components/EventTimeline";
import { RunGraphsPanel } from "../components/GameplayGraphs";
import { GuideCompact } from "../components/HowToPlay";
import { MapView } from "../components/MapView";
import { MindPanel } from "../components/MindPanel";
import { MissionBar } from "../components/MissionBar";
import { ObjectivePanel } from "../components/ObjectivePanel";
import { Storybook } from "../components/Storybook";
import { TeamPanel } from "../components/TeamPanel";
import { Toasts } from "../components/Toasts";
import { ToonAvatar } from "../components/ToonAvatar";
import { TopBar } from "../components/TopBar";
import { Badge, Button, PlainPanels } from "../components/ui";
import { projectedSimTime } from "../game/geometry";
import { useRun } from "../hooks/useRun";
import { useSpokenReplies } from "../hooks/useSpeech";
import type { PlayerAction, RunSession } from "../services/api";
import type { ActionResult, Health, StateView } from "../types/api";
import { prettyAbility } from "../types/scenario";
import { EndingScreen } from "./EndingScreen";

type Tab = "you" | "team" | "story" | "log" | "graphs" | "guide";

function useTicker(ms: number): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(id);
  }, [ms]);
  return now;
}

export function GameScreen({ session, health, onRestart, onMenu, onOtherMode, onLost }: {
  session: RunSession;
  health: Health | null;
  onRestart: () => void;
  onMenu: () => void;
  onOtherMode: (current: StateView) => void;
  onLost: () => void;
}) {
  const run = useRun(session);
  const wall = useTicker(250);
  const [focus, setFocus] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<ActionResult | null>(null);
  const [showEnding, setShowEnding] = useState(false);
  const [lastCommand, setLastCommand] = useState<ActionResult | null>(null);
  const [lastSay, setLastSay] = useState<ActionResult | null>(null);
  const [lastTwist, setLastTwist] = useState<ActionResult | null>(null);
  const [tab, setTab] = useState<Tab | null>(null);
  const [mindOf, setMindOf] = useState<string | null>(null);
  const [seenPages, setSeenPages] = useState(0);
  const [voices, setVoices] = useState(() => {
    try {
      return localStorage.getItem("offscript.voices") === "on";
    } catch {
      return false;
    }
  });
  const setVoicesSaved = (on: boolean) => {
    setVoices(on);
    try {
      localStorage.setItem("offscript.voices", on ? "on" : "off");
    } catch {
      // per-browser preference only; fine to lose
    }
  };
  useSpokenReplies(run.events, voices, run.state?.run.player_character ?? null);

  const { state } = run;
  const finished = state?.run.status === "finished" && !!state.story.ending;
  const pages = state?.story.chapters?.length ?? 0;
  const isGame = !!state?.run.player_character;
  const active: Tab = tab ?? (isGame ? "you" : "story");

  useEffect(() => {
    if (run.lost) onLost();
  }, [run.lost, onLost]);

  useEffect(() => {
    if (!finished) return;
    const id = setTimeout(() => setShowEnding(true), 3500);
    return () => clearTimeout(id);
  }, [finished]);

  useEffect(() => {
    if (active === "story") setSeenPages(pages);
  }, [active, pages]);

  const placeName = useMemo(() => {
    const names = new Map(state?.locations.map((l) => [l.id, l.name]) ?? []);
    return (id: string) => names.get(id) ?? id;
  }, [state?.locations]);

  if (!state) {
    return (
      <div className="grid min-h-dvh place-items-center text-muted">
        <span className="flex items-center gap-2"><Loader2 className="animate-spin" /> Reaching Aether Island…</span>
        {run.error && <p className="text-danger">{run.error}</p>}
      </div>
    );
  }

  if (showEnding && finished) {
    return <EndingScreen state={state} session={session} onRestart={onRestart} onMenu={onMenu} onOtherMode={() => onOtherMode(state)} />;
  }

  const running = state.run.status === "running";
  const simNow = projectedSimTime(state, run.receivedAt, wall);
  const me = state.characters.find((c) => c.id === state.run.player_character) ?? null;
  const others = me && !me.travel ? state.characters.filter((c) => c.id !== me.id && !c.travel && c.location_id === me.location_id) : [];
  const objName = (id: string) => state.objects.find((o) => o.id === id)?.name ?? id;

  const mindCharacter = active === "team" && mindOf ? state.characters.find((c) => c.id === mindOf) ?? null : null;
  const mindOverlay = mindCharacter ? { name: mindCharacter.name, beliefs: mindCharacter.mind.beliefs } : null;
  const openMind = (id: string) => {
    setMindOf(id);
    setFocus(id);
    setTab("team");
  };
  const focusOnMap = (id: string) => {
    setFocus(id);
    if (mindCharacter) setMindOf(id); // with a mind open, clicking a character on the map looks inside theirs
  };

  const act = async (action: PlayerAction) => setLastResult(await run.act(action));
  const command = async (text: string) => setLastCommand(await run.command(text));
  const say = async (text: string) => setLastSay(await run.say(text));
  const addTwist = async (text: string) => setLastTwist(await run.twist(text));
  const talk = async (target: string, message: string) => setLastResult(await run.talk(target, message));

  const tabs: { id: Tab; label: string; icon: ReactNode; dot?: boolean }[] = [
    ...(me ? [{ id: "you" as const, label: "You", icon: <User size={14} /> }] : []),
    { id: "team", label: "Team", icon: <Users size={14} /> },
    { id: "story", label: "Story", icon: <BookOpen size={14} />, dot: pages > seenPages && active !== "story" },
    { id: "log", label: "Log", icon: <ScrollText size={14} /> },
    { id: "graphs", label: "Graphs", icon: <BarChart3 size={14} /> },
    { id: "guide", label: "Guide", icon: <CircleHelp size={14} /> },
  ];

  return (
    <div className="flex min-h-dvh flex-col lg:h-dvh lg:overflow-hidden">
      <TopBar state={state} health={health} simNow={simNow} pending={run.pending}
        onPause={(p) => void run.pause(p)} onSkip={() => void run.advance(6)} onRestart={onRestart} onMenu={onMenu} />
      <Toasts events={run.events} />

      {finished && (
        <div className="flex flex-wrap items-center justify-center gap-3 border-b-[3px] border-ink bg-[#fff3bf] px-4 py-2 text-sm">
          <Flag size={16} className="text-amber" />
          <b className="font-display text-ink">{state.story.ending!.title}</b>
          <span className="text-muted">{state.story.ending!.explanation}</span>
          <Button variant="primary" onClick={() => setShowEnding(true)}>See the ending</Button>
        </div>
      )}
      {run.error && !run.lost && (
        <p role="alert" className="bg-danger/15 px-4 py-1 text-center text-sm text-danger">Connection problem: {run.error}</p>
      )}

      {/* On large screens the game is one fixed frame: no page scroll, and the map takes all the room that is left. */}
      <main className="mx-auto grid w-full max-w-[1920px] flex-1 content-start gap-3 p-3 lg:min-h-0 lg:grid-cols-[minmax(0,1fr)_360px] lg:grid-rows-[auto_minmax(0,1fr)] 2xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="lg:col-span-2">
          <MissionBar state={state} />
        </div>

        {/* The map fills the column; the radio sits right under it. */}
        <div className="flex w-full min-w-0 flex-col gap-3 lg:min-h-0">
          <MapView className="lg:min-h-0 lg:flex-1" state={state} receivedAt={run.receivedAt} events={run.events} focus={focus}
            onFocus={focusOnMap} mind={mindOverlay} />
          {me && running && (
            <CommandBar disabled={false} pending={run.pending} lastResult={lastCommand} sayResult={lastSay}
              twistResult={lastTwist} twists={state.story.twists} now={simNow} voices={voices} onVoices={setVoicesSaved}
              onCommand={(t) => void command(t)} onSay={(t) => void say(t)} onTwist={(t) => void addTwist(t)} />
          )}
        </div>

        <aside className="panel flex min-h-[28rem] min-w-0 flex-col overflow-hidden lg:min-h-0">
          <div role="tablist" aria-label="Game panels" className="flex shrink-0 gap-1 border-b-[3px] border-ink bg-[#fff9db] p-1.5">
            {tabs.map((t) => (
              <button key={t.id} type="button" role="tab" aria-selected={active === t.id} onClick={() => setTab(t.id)}
                className={`relative flex flex-1 items-center justify-center gap-1 rounded-xl border-2 px-1.5 py-1.5 text-xs font-bold transition
                  ${active === t.id ? "border-ink bg-white text-ink shadow-[0_2px_0_#1d2142]" : "border-transparent text-muted hover:text-ink"}`}>
                {t.icon} {t.label}
                {t.dot && <span className="absolute right-1.5 top-1 size-2 rounded-full bg-danger" aria-label="new page" />}
              </button>
            ))}
          </div>

          <div role="tabpanel" className="scroll-thin min-h-0 flex-1 overflow-y-auto p-4">
            <PlainPanels.Provider value>
              {active === "you" && me && (
                <div className="space-y-4">
                  <section className="flex items-center gap-3">
                    <ToonAvatar id={me.id} color={me.color} size={48} />
                    <div className="min-w-0">
                      <p className="font-display text-lg leading-tight">You are {me.name}</p>
                      <p className="text-sm text-muted">
                        {me.travel ? `On the road to the ${placeName(me.travel.to_location)}` : `At the ${placeName(me.location_id ?? "")}`}
                      </p>
                      <p className="mt-0.5 flex flex-wrap items-center gap-1 text-xs text-muted">
                        <Package size={12} /> {me.inventory.length ? me.inventory.map(objName).join(", ") : "Carrying nothing"}
                      </p>
                    </div>
                  </section>
                  <div className="flex flex-wrap gap-1">
                    {me.abilities.map((a) => <Badge key={a} tone="amber">{prettyAbility(a)}</Badge>)}
                  </div>
                  {running ? (
                    <>
                      <ActionPanel me={me} options={state.available_actions} now={simNow} pending={run.pending}
                        lastResult={lastResult} onAct={(a) => void act(a)} placeName={placeName} />
                      {others.length > 0 && (
                        <DialoguePanel me={me} others={others} events={run.events} pending={run.pending}
                          busy={!!(me.travel ?? me.activity)} onSend={(t, m) => void talk(t, m)} />
                      )}
                    </>
                  ) : (
                    <p className="text-sm text-muted">The run is over.</p>
                  )}
                </div>
              )}
              {active === "team" && mindCharacter && (
                <MindPanel character={mindCharacter} characters={state.characters} now={simNow}
                  nameOf={(id) => state.characters.find((c) => c.id === id)?.name ?? id}
                  onPick={openMind} onBack={() => setMindOf(null)} />
              )}
              {active === "team" && !mindCharacter && (
                <TeamPanel characters={state.characters} objects={state.objects} placeName={placeName} now={simNow}
                  focus={focus} onFocus={setFocus} onOpenMind={openMind} />
              )}
              {active === "story" && (
                <div className="flex h-full flex-col gap-4">
                  <Storybook chapters={state.story.chapters ?? []} className="min-h-0 flex-1" />
                  <ObjectivePanel state={state} />
                </div>
              )}
              {active === "log" && <EventTimeline events={run.events} className="h-full" />}
              {active === "graphs" && (
                // Live: re-fetched every 15 s of game time while this tab is open.
                <RunGraphsPanel session={session} refresh={Math.floor(state.clock.now / 15)} bare />
              )}
              {active === "guide" && <GuideCompact game={!!me} />}
            </PlainPanels.Provider>
          </div>
        </aside>
      </main>
    </div>
  );
}
