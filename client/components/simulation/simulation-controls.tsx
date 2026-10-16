"use client";
import { useState } from "react";
import type { Edge, Node } from "@xyflow/react";
import { Play, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSimulation } from "@/hooks/use-simulation";
export function SimulationControls({
  nodes,
  edges,
}: {
  nodes: Node[];
  edges: Edge[];
}) {
  const [duration, setDuration] = useState(10);
  const { status, progress, runSimulation, stopSimulation } = useSimulation();
  const running = status === "connecting" || status === "running";
  return (
    <div className="flex flex-wrap items-center gap-3">
      <label className="text-sm">
        Duration{" "}
        <select
          aria-label="Simulation duration"
          value={duration}
          onChange={(event) => setDuration(Number(event.target.value))}
          disabled={running}
          className="rounded-md border bg-background px-3 py-2 text-sm"
        >
          {[5, 10, 30, 60].map((value) => (
            <option key={value} value={value}>
              {value} seconds
            </option>
          ))}
        </select>
      </label>
      {running ? (
        <Button variant="destructive" onClick={stopSimulation}>
          <Square className="size-4" />
          Stop
        </Button>
      ) : (
        <Button onClick={() => runSimulation(nodes, edges, duration)}>
          <Play className="size-4" />
          Run Simulation
        </Button>
      )}
      <span role="status" className="text-sm text-muted-foreground">
        {running
          ? `${status === "connecting" ? "Connecting" : "Running"} · ${progress.toFixed(0)}%`
          : status === "completed"
            ? "Completed · 100%"
            : status === "error"
              ? "Simulation failed"
              : "Ready"}
      </span>
    </div>
  );
}
