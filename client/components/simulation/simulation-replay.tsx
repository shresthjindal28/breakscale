"use client";
import { useEffect, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type NodeProps,
} from "@xyflow/react";
import { Button } from "@/components/ui/button";
import { simulationHistoryApi } from "@/lib/api/simulation-history";
import { buildRequestAnimations } from "@/lib/simulation/trace-animation";
import { usePlaybackStore } from "@/stores/playback-store";
import type { SavedSimulation } from "@/types/simulation-history";
import { PlaybackControls } from "@/components/simulation/playback-controls";
import { RequestAnimationOverlay } from "@/components/simulation/request-animation-overlay";
function ReplayNode({ data }: NodeProps) {
  return (
    <div className="min-w-40 rounded-lg border bg-card px-4 py-3 text-sm shadow-sm">
      <Handle type="target" position={Position.Top} isConnectable={false} />
      {typeof data.label === "string" ? data.label : "Component"}
      <Handle type="source" position={Position.Bottom} isConnectable={false} />
    </div>
  );
}
const nodeTypes = { default: ReplayNode };
export function SimulationReplay({
  simulationId,
  onClose,
}: {
  simulationId: string;
  onClose: () => void;
}) {
  const [run, setRun] = useState<SavedSimulation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const trace = usePlaybackStore((state) => state.trace);
  useEffect(() => {
    let active = true;
    usePlaybackStore.getState().reset();
    Promise.all([
      simulationHistoryApi.getTrace(simulationId),
      simulationHistoryApi.get(simulationId),
    ])
      .then(([trace, simulation]) => {
        if (!active) return;
        if (
          !simulation.graph_snapshot?.nodes ||
          !simulation.graph_snapshot.edges
        )
          throw new Error("This run has no saved architecture for replay");
        const validEdges = new Set(
          simulation.graph_snapshot.edges.map(
            (edge) => `${edge.source}->${edge.target}`,
          ),
        );
        usePlaybackStore
          .getState()
          .load(
            trace,
            buildRequestAnimations(trace.events, validEdges),
            simulation.duration_seconds,
          );
        setRun(simulation);
      })
      .catch((err) => {
        if (active)
          setError(
            err instanceof Error ? err.message : "Unable to load replay",
          );
      });
    return () => {
      active = false;
      usePlaybackStore.getState().reset();
    };
  }, [simulationId]);
  const graph = run?.graph_snapshot;
  return (
    <section
      aria-label="Simulation replay"
      className="space-y-4 rounded-xl border p-5"
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-lg font-semibold">
          Replay · {simulationId.slice(0, 8)}
        </h3>
        <Button variant="outline" onClick={onClose}>
          Close replay
        </Button>
      </div>
      {error ? (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      ) : !graph || !trace ? (
        <p>Loading replay...</p>
      ) : (
        <>
          {trace.truncated && (
            <p role="status" className="text-sm text-amber-600">
              Trace truncated: {trace.dropped_events.toLocaleString()} events
              were dropped. Only the first recorded events are shown.
            </p>
          )}
          {!trace.events.length && (
            <p className="text-sm text-muted-foreground">
              No trace is available. This run may predate event tracing; it does
              not mean no requests were processed.
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            Read-only saved architecture. Markers interpolate request
            progression between recorded node entries, including processing
            time; background jobs are not traced. Up to 200 markers are visible.
          </p>
          <div className="h-[400px] overflow-hidden rounded-xl border">
            <ReactFlowProvider>
              <ReactFlow
                nodes={graph.nodes.map((node) => ({
                  id: node.id,
                  position: node.position ?? { x: 0, y: 0 },
                  data: {
                    ...node.data,
                    label:
                      typeof node.data.label === "string"
                        ? node.data.label
                        : node.id,
                  },
                }))}
                edges={graph.edges}
                nodeTypes={nodeTypes}
                nodesDraggable={false}
                nodesConnectable={false}
                elementsSelectable={false}
                fitView
              >
                <Background />
                <Controls showInteractive={false} />
                <RequestAnimationOverlay />
              </ReactFlow>
            </ReactFlowProvider>
          </div>
          <PlaybackControls />
        </>
      )}
    </section>
  );
}
