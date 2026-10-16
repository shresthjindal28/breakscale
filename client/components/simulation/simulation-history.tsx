"use client";
import { useState } from "react";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { SavedSimulation } from "@/types/simulation-history";
export function SimulationHistory({
  runs,
  loading,
  onDelete,
  onCompare,
  onReplay,
}: {
  runs: SavedSimulation[];
  loading: boolean;
  onDelete: (id: string) => Promise<void>;
  onCompare: (a: string, b: string) => void;
  onReplay?: (id: string) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const eligible = selected.filter((id) =>
    runs.some((run) => run.id === id && run.status === "completed"),
  );
  const remove = async (id: string) => {
    setDeleting(id);
    setError(null);
    try {
      await onDelete(id);
      setSelected((previous) => previous.filter((value) => value !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to delete run");
    } finally {
      setDeleting(null);
    }
  };
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-lg font-semibold">Simulation History</h3>
        <Button
          disabled={eligible.length !== 2 || loading || !!deleting}
          onClick={() => onCompare(eligible[0], eligible[1])}
        >
          Compare Selected
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {loading ? (
        <p>Loading simulations...</p>
      ) : !runs.length ? (
        <p className="text-sm text-muted-foreground">
          No saved simulations yet.
        </p>
      ) : (
        runs.map((run) => (
          <div
            key={run.id}
            className="flex items-center gap-3 rounded-lg border p-3"
          >
            <input
              type="checkbox"
              checked={eligible.includes(run.id)}
              disabled={run.status !== "completed"}
              onChange={() =>
                setSelected(
                  eligible.includes(run.id)
                    ? eligible.filter((id) => id !== run.id)
                    : [...eligible.slice(-1), run.id],
                )
              }
              aria-label={`Select simulation ${run.id}`}
            />
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">Run {run.id.slice(0, 8)}</p>
              <p className="text-xs text-muted-foreground">
                {run.created_at
                  ? new Date(run.created_at).toLocaleString()
                  : "Unknown date"}{" "}
                · {run.duration_seconds}s · {run.status}
              </p>
            </div>
            {onReplay && run.status === "completed" && (
              <Button
                variant="outline"
                onClick={() => onReplay(run.id)}
                aria-label={`Replay simulation ${run.id}`}
              >
                Replay
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              disabled={
                !!deleting ||
                run.status === "running" ||
                run.status === "pending"
              }
              onClick={() => void remove(run.id)}
              aria-label={`Delete simulation ${run.id}`}
            >
              <Trash2 className="size-4" />
            </Button>
          </div>
        ))
      )}
    </div>
  );
}
