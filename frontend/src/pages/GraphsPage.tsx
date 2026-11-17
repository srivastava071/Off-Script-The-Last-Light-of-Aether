import { ArrowLeft, BarChart3, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { AllRunsGraphs, RunGraphsPanel } from "../components/GameplayGraphs";
import { Button, Panel } from "../components/ui";
import { api, type RunSession } from "../services/api";
import type { RunSummary } from "../types/api";

/** Gameplay graphs: every finished run, and the detailed graphs of the most recent run on this device. */
export function GraphsPage({ latest, onBack }: { latest: RunSession | null; onBack: () => void }) {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.finishedRuns().then(setRuns).catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className="mx-auto max-w-6xl space-y-4 px-4 py-8">
      <div className="flex items-center gap-3">
        <Button onClick={onBack}><ArrowLeft size={14} /> Main menu</Button>
        <h1 className="flex items-center gap-2 font-display text-3xl text-ink"><BarChart3 /> Gameplay graphs</h1>
      </div>

      <Panel title="All finished runs" icon={<BarChart3 size={16} />}>
        {error ? <p className="text-sm text-danger">Could not load the runs: {error}</p>
          : !runs ? <p className="flex justify-center text-muted"><Loader2 className="animate-spin" /></p>
          : runs.length === 0 ? <p className="text-sm text-muted">No finished runs yet. Play or watch a game to the end, then come back.</p>
          : <AllRunsGraphs runs={runs} />}
      </Panel>

      {latest && (
        <div>
          <h2 className="mb-2 font-display text-xl text-ink">Your latest run, in detail</h2>
          <RunGraphsPanel session={latest} wide />
        </div>
      )}
    </div>
  );
}
