"use client";
import { useCallback, useEffect, useRef } from "react";
import type { Edge, Node } from "@xyflow/react";
import { connectSimulation } from "@/lib/api/simulation";
import { toBackendGraph } from "@/lib/simulation/graph-adapter";
import { useSimulationStore } from "@/stores/simulation-store";
export function useSimulation() {
  const socketRef = useRef<WebSocket | null>(null);
  const runIdRef = useRef(0);
  const state = useSimulationStore();
  const { start, setRunning, addSnapshot, complete, fail, reset } = state;
  const runSimulation = useCallback(
    (nodes: Node[], edges: Edge[], duration = 10) => {
      const runId = ++runIdRef.current;
      socketRef.current?.close();
      start(duration);
      try {
        if (!Number.isFinite(duration) || duration <= 0 || duration > 300)
          throw new Error("Duration must be between 0 and 300 seconds");
        const graph = toBackendGraph(nodes, edges);
        if (!graph.nodes.length)
          throw new Error("Add components before running");
        socketRef.current = connectSimulation({
          graph,
          durationSeconds: duration,
          onEvent: (event) => {
            if (
              runId !== runIdRef.current ||
              useSimulationStore.getState().status === "error"
            )
              return;
            switch (event.type) {
              case "simulation.started":
                setRunning();
                break;
              case "simulation.metrics":
                addSnapshot(event.data);
                break;
              case "simulation.completed":
                complete(event.data);
                socketRef.current?.close();
                break;
              case "simulation.error":
                fail(event.data.message);
                socketRef.current?.close();
                break;
            }
          },
          onError: (err) => {
            if (runId === runIdRef.current) {
              fail(err.message);
              socketRef.current?.close();
            }
          },
          onClose: () => {
            if (runId !== runIdRef.current) return;
            const status = useSimulationStore.getState().status;
            if (status === "connecting" || status === "running")
              fail("Connection closed before simulation finished");
          },
        });
      } catch (err) {
        fail(err instanceof Error ? err.message : "Unable to start simulation");
      }
    },
    [start, setRunning, addSnapshot, complete, fail],
  );
  const stopSimulation = useCallback(() => {
    ++runIdRef.current;
    socketRef.current?.close();
    socketRef.current = null;
    reset();
  }, [reset]);
  useEffect(
    () => () => {
      ++runIdRef.current;
      socketRef.current?.close();
      const status = useSimulationStore.getState().status;
      if (status === "connecting" || status === "running") reset();
    },
    [reset],
  );
  return { ...state, runSimulation, stopSimulation };
}
