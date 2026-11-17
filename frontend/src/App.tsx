import { useCallback, useEffect, useState } from "react";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { Briefing, hasBeenBriefed } from "./components/HowToPlay";
import { CharacterSelect } from "./pages/CharacterSelect";
import { GameScreen } from "./pages/GameScreen";
import { GraphsPage } from "./pages/GraphsPage";
import { MainMenu } from "./pages/MainMenu";
import { api, loadSession, saveSession, type RunSession } from "./services/api";
import type { CharacterId, Health, StateView } from "./types/api";
import type { Scenario } from "./types/scenario";

type Screen = { name: "menu" } | { name: "select" } | { name: "graphs" } | { name: "brief"; player: CharacterId }
  | { name: "play"; session: RunSession };

export default function App() {
  const [screen, setScreen] = useState<Screen>({ name: "menu" });
  const [health, setHealth] = useState<Health | null>(null);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [saved, setSaved] = useState<RunSession | null>(() => loadSession());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setError("Cannot reach the game server. Is the backend running on port 8000?"));
    api.scenario().then(setScenario).catch(() => undefined);
  }, []);

  const play = useCallback((session: RunSession) => {
    saveSession(session);
    setSaved(session);
    setScreen({ name: "play", session });
  }, []);

  const begin = useCallback(async (mode: "default" | "game", player?: CharacterId) => {
    setBusy(true);
    setError(null);
    try {
      const created = await api.createRun(mode, player);
      const session = { runId: created.run_id, token: created.token };
      await api.start(session);
      play(session);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [play]);

  const restart = useCallback(async (session: RunSession) => {
    try {
      const created = await api.restart(session);
      const next = { runId: created.run_id, token: created.token };
      await api.start(next);
      play(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setScreen({ name: "menu" });
    }
  }, [play]);

  const toMenu = useCallback(() => setScreen({ name: "menu" }), []);
  const lost = useCallback(() => {
    saveSession(null);
    setSaved(null);
    setError("That run is no longer available. Start a new one.");
    setScreen({ name: "menu" });
  }, []);
  const otherMode = useCallback((state: StateView) => {
    if (state.run.mode === "game") void begin("default");
    else setScreen({ name: "select" });
  }, [begin]);

  if (screen.name === "play") {
    return (
      <ErrorBoundary onReset={toMenu}>
        <GameScreen key={screen.session.runId} session={screen.session} health={health}
          onRestart={() => void restart(screen.session)} onMenu={toMenu} onOtherMode={otherMode} onLost={lost} />
      </ErrorBoundary>
    );
  }
  if (screen.name === "graphs") {
    return <GraphsPage latest={saved} onBack={toMenu} />;
  }
  if (screen.name === "brief") {
    // First Game Mode run on this device: explain the game before the storm clock starts.
    return <Briefing scenario={scenario} player={screen.player} busy={busy}
      onBack={() => setScreen({ name: "select" })} onStart={() => void begin("game", screen.player)} />;
  }
  if (screen.name === "select") {
    return <CharacterSelect scenario={scenario} busy={busy} error={error} onBack={toMenu}
      onSelect={(id) => (hasBeenBriefed() ? void begin("game", id) : setScreen({ name: "brief", player: id }))} />;
  }
  return (
    <MainMenu scenario={scenario} health={health} canResume={!!saved} busy={busy} error={error}
      onDefault={() => void begin("default")} onGame={() => { setError(null); setScreen({ name: "select" }); }}
      onResume={() => saved && setScreen({ name: "play", session: saved })}
      onGraphs={() => setScreen({ name: "graphs" })} />
  );
}
