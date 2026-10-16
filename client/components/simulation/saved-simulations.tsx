"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { workspaceApi } from "@/lib/api/simulation-history";
import { toBackendGraph } from "@/lib/simulation/graph-adapter";
import { workspaceSchema } from "@/lib/schemas/workspace";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { useSimulationHistory } from "@/hooks/use-simulation-history";
import { SavedRunControls } from "@/components/simulation/saved-run-controls";
import { SimulationHistory } from "@/components/simulation/simulation-history";
import { SimulationComparison } from "@/components/simulation/simulation-comparison";
import type {
  SavedWorkspace,
  SavedSimulationResult,
} from "@/types/simulation-history";
import { SimulationReplay } from "@/components/simulation/simulation-replay";

export function SavedSimulations() {
  const canvas = useWorkspaceStore();
  const [replayId, setReplayId] = useState<string | null>(null);
  const [workspaces, setWorkspaces] = useState<SavedWorkspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [name, setName] = useState("Playground workspace");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [comparing, setComparing] = useState(false);
  const [comparison, setComparison] = useState<{
    workspaceId: string;
    first: SavedSimulationResult;
    second: SavedSimulationResult;
  } | null>(null);
  const history = useSimulationHistory(workspaceId);
  useEffect(() => {
    let active = true;
    workspaceApi
      .list()
      .then((data) => {
        if (active) setWorkspaces(data);
      })
      .catch((err) => {
        if (active)
          setError(
            err instanceof Error ? err.message : "Unable to load workspaces",
          );
      });
    return () => {
      active = false;
    };
  }, []);
  async function saveWorkspace() {
    if (!name.trim()) throw new Error("Enter a workspace name");
    const saved = await workspaceApi.save(
      workspaceId,
      name.trim(),
      toBackendGraph(canvas.nodes, canvas.edges),
    );
    setWorkspaces((previous) => [
      saved,
      ...previous.filter((item) => item.id !== saved.id),
    ]);
    setWorkspaceId(saved.id);
    setNotice("Current canvas saved to PostgreSQL.");
    return saved;
  }
  async function saveAndRun(duration: number) {
    setBusy(true);
    setError(null);
    setComparison(null);
    try {
      await saveWorkspace();
      await history.saveRun(duration);
      setNotice("Current canvas saved and simulation completed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save run");
    } finally {
      setBusy(false);
    }
  }
  async function compare(a: string, b: string) {
    if (!workspaceId) return;
    setComparing(true);
    setError(null);
    try {
      const [first, second] = await Promise.all([
        history.loadResult(a),
        history.loadResult(b),
      ]);
      setComparison({ workspaceId, first, second });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to compare runs");
    } finally {
      setComparing(false);
    }
  }
  function selectWorkspace(id: string) {
    setComparison(null);
    setReplayId(null);
    setError(null);
    setNotice("");
    if (!id) {
      setWorkspaceId(null);
      setName("Playground workspace");
      return;
    }
    const workspace = workspaces.find((item) => item.id === id);
    if (!workspace) return;
    try {
      const snapshot = workspaceSchema.parse({
        version: 1,
        savedAt: new Date().toISOString(),
        nodes: workspace.graph_data.nodes.map((node) => ({
          id: node.id,
          position: node.position ?? { x: 0, y: 0 },
          data: {
            ...node.data,
            label:
              typeof node.data.label === "string" ? node.data.label : node.id,
            componentType: node.type,
          },
        })),
        edges: workspace.graph_data.edges,
      });
      canvas.restore(snapshot);
      setWorkspaceId(id);
      setName(workspace.name);
    } catch {
      setError(
        "This workspace has no valid saved architecture. Save a new workspace from the canvas.",
      );
    }
  }
  const visibleComparison =
    comparison?.workspaceId === workspaceId &&
    history.runs.some((run) => run.id === comparison.first.simulation_id) &&
    history.runs.some((run) => run.id === comparison.second.simulation_id)
      ? comparison
      : null;
  return (
    <section
      className="space-y-5 rounded-xl border p-5"
      aria-label="Saved simulations"
    >
      <h2 className="text-xl font-semibold">Saved Simulations</h2>
      <p className="text-sm text-muted-foreground">
        Save the workspace to PostgreSQL first. Save &amp; Run saves the current
        canvas again before running.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">
          Workspace
          <select
            aria-label="Saved workspace"
            value={workspaceId ?? ""}
            disabled={busy || history.saving || comparing}
            onChange={(event) => selectWorkspace(event.target.value)}
            className="mt-1 block max-w-64 rounded-md border bg-background px-3 py-2"
          >
            <option value="">New workspace</option>
            {workspaces.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          Workspace name
          <input
            aria-label="Workspace name"
            maxLength={150}
            disabled={busy}
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="mt-1 block rounded-md border bg-background px-3 py-2"
          />
        </label>
        <Button
          disabled={busy || history.saving}
          variant="outline"
          onClick={() => {
            setBusy(true);
            setError(null);
            void saveWorkspace()
              .catch((err) =>
                setError(err instanceof Error ? err.message : "Save failed"),
              )
              .finally(() => setBusy(false));
          }}
        >
          Save workspace to server
        </Button>
        <Button
          variant="outline"
          disabled={!workspaceId || busy || history.loading}
          onClick={() => void history.refresh()}
        >
          Refresh history
        </Button>
      </div>
      <SavedRunControls
        disabled={!workspaceId || comparing}
        saving={busy || history.saving}
        onRun={saveAndRun}
      />
      {(error || history.error) && (
        <p role="alert" className="text-sm text-destructive">
          {error ?? history.error}
        </p>
      )}
      {notice && (
        <p role="status" className="text-sm text-muted-foreground">
          {notice}
        </p>
      )}
      <SimulationHistory
        key={workspaceId ?? "new"}
        runs={history.runs}
        loading={history.loading || comparing}
        onDelete={async (id) => {
          await history.deleteRun(id);
          if (replayId === id) setReplayId(null);
        }}
        onReplay={(id) => setReplayId(id)}
        onCompare={(a, b) => void compare(a, b)}
      />
      {replayId && (
        <SimulationReplay
          key={replayId}
          simulationId={replayId}
          onClose={() => setReplayId(null)}
        />
      )}
      {visibleComparison && (
        <SimulationComparison
          first={visibleComparison.first}
          second={visibleComparison.second}
          firstRun={history.runs.find(
            (run) => run.id === visibleComparison.first.simulation_id,
          )}
          secondRun={history.runs.find(
            (run) => run.id === visibleComparison.second.simulation_id,
          )}
        />
      )}
    </section>
  );
}
