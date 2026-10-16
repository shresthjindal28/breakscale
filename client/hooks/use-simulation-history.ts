"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { simulationHistoryApi } from "@/lib/api/simulation-history";
import type {
  SavedSimulation,
  SavedSimulationResult,
} from "@/types/simulation-history";
export function useSimulationHistory(workspaceId: string | null) {
  const [runs, setRuns] = useState<SavedSimulation[]>([]);
  const [runsWorkspace, setRunsWorkspace] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, SavedSimulationResult>>(
    {},
  );
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);
  const refresh = useCallback(async () => {
    const token = ++generation.current;
    if (!workspaceId) {
      setRuns([]);
      setResults({});
      setError(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await simulationHistoryApi.list(workspaceId);
      if (token === generation.current) {
        setRuns(data);
        setRunsWorkspace(workspaceId);
      }
    } catch (err) {
      if (token === generation.current)
        setError(err instanceof Error ? err.message : "Unable to load runs");
    } finally {
      if (token === generation.current) setLoading(false);
    }
  }, [workspaceId]);
  const invalidate = useCallback(() => {
    ++generation.current;
  }, []);
  useEffect(() => {
    const timer = setTimeout(() => {
      void refresh();
    }, 0);
    return () => {
      clearTimeout(timer);
      invalidate();
    };
  }, [refresh, invalidate]);
  const saveRun = useCallback(
    async (duration: number) => {
      if (!workspaceId) throw new Error("Save the workspace before running");
      setSaving(true);
      setError(null);
      try {
        const run = await simulationHistoryApi.create(workspaceId, duration);
        await refresh();
        return run;
      } catch (err) {
        await refresh();
        setError(err instanceof Error ? err.message : "Simulation failed");
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [workspaceId, refresh],
  );
  const loadResult = useCallback(
    async (id: string) => {
      if (results[id]) return results[id];
      const token = generation.current;
      const result = await simulationHistoryApi.getResults(id);
      if (token === generation.current)
        setResults((previous) => ({ ...previous, [id]: result }));
      return result;
    },
    [results],
  );
  const deleteRun = useCallback(
    async (id: string) => {
      try {
        await simulationHistoryApi.delete(id);
        setResults((previous) => {
          const next = { ...previous };
          delete next[id];
          return next;
        });
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to delete run");
        throw err;
      }
    },
    [refresh],
  );
  return {
    runs: runsWorkspace === workspaceId ? runs : [],
    results,
    loading,
    saving,
    error,
    refresh,
    saveRun,
    loadResult,
    deleteRun,
  };
}
