import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { toBackendGraph } from "@/lib/simulation/graph-adapter";
import { parseSimulationEvent } from "@/lib/api/simulation";
import { useSimulation } from "@/hooks/use-simulation";
import { useSimulationStore } from "@/stores/simulation-store";
import { workspaceSchema } from "@/lib/schemas/workspace";

const nodes = [
  {
    id: "client",
    type: "customNode",
    position: { x: 0, y: 0 },
    data: { componentType: "client", rps: 20 },
  },
];
class FakeSocket {
  static instances: FakeSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn(() => this.onclose?.());
  constructor(public url: string) {
    FakeSocket.instances.push(this);
  }
  emit(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
}
afterEach(() => {
  vi.unstubAllGlobals();
  useSimulationStore.getState().reset();
  FakeSocket.instances = [];
});
test("adapter maps custom types and rejects invalid graphs", () => {
  expect(toBackendGraph(nodes, []).nodes[0]).toMatchObject({
    type: "client",
    data: { rps: 20 },
  });
  expect(() =>
    toBackendGraph(nodes, [{ id: "e", source: "client", target: "missing" }]),
  ).toThrow("missing source");
  expect(() => toBackendGraph([{ ...nodes[0], data: {} }], [])).toThrow(
    "Unsupported",
  );
});
test("saved workspaces preserve simulation data", () => {
  const result = workspaceSchema.parse({
    version: 1,
    savedAt: new Date().toISOString(),
    nodes: [
      {
        ...nodes[0],
        data: { label: "Client", componentType: "client", rps: 20 },
      },
    ],
    edges: [],
  });
  expect(result.nodes[0].data.rps).toBe(20);
  expect(result.nodes[0].data.componentType).toBe("client");
});
test("event parser matches backend error envelope and rejects malformed messages", () => {
  expect(
    parseSimulationEvent(
      '{"type":"simulation.error","data":{"message":"Invalid graph"}}',
    ).type,
  ).toBe("simulation.error");
  expect(() =>
    parseSimulationEvent('{"type":"simulation.metrics","data":{}}'),
  ).toThrow();
});
test("hook sends graph, handles errors, and ignores stale runs", () => {
  vi.stubGlobal("WebSocket", FakeSocket);
  const { result, unmount } = renderHook(() => useSimulation());
  act(() => result.current.runSimulation(nodes, [], 10));
  const first = FakeSocket.instances[0];
  act(() => first.onopen?.());
  expect(JSON.parse(first.send.mock.calls[0][0]).graph.nodes[0].type).toBe(
    "client",
  );
  act(() =>
    first.emit({
      type: "simulation.started",
      data: { duration_seconds: 10, sample_interval: 0.5 },
    }),
  );
  expect(result.current.status).toBe("running");
  act(() => result.current.runSimulation(nodes, [], 5));
  act(() =>
    first.emit({ type: "simulation.error", data: { message: "Old error" } }),
  );
  expect(result.current.status).toBe("connecting");
  const second = FakeSocket.instances[1];
  act(() =>
    second.emit({
      type: "simulation.error",
      data: { message: "Graph invalid" },
    }),
  );
  expect(result.current.error).toBe("Graph invalid");
  act(() => result.current.stopSimulation());
  expect(result.current.status).toBe("idle");
  unmount();
});
test("hook retains final results and completes at 100 percent", () => {
  vi.stubGlobal("WebSocket", FakeSocket);
  const { result } = renderHook(() => useSimulation());
  act(() => result.current.runSimulation(nodes, []));
  const socket = FakeSocket.instances[0];
  const jobs = {
    submitted: 0,
    completed: 0,
    dead_lettered: 0,
    failed_attempts: 0,
    latencies_ms: [],
  };
  act(() =>
    socket.emit({
      type: "simulation.completed",
      data: {
        generated: 1,
        completed: 1,
        failed: 0,
        latencies_ms: [10],
        node_metrics: {},
        total_retries: 0,
        component_attempts: 1,
        retry_amplification: 1,
        job_metrics: jobs,
      },
    }),
  );
  expect(result.current.status).toBe("completed");
  expect(result.current.progress).toBe(100);
  expect(result.current.result?.completed).toBe(1);
});
test("early socket closure reports an error", () => {
  vi.stubGlobal("WebSocket", FakeSocket);
  const { result } = renderHook(() => useSimulation());
  act(() => result.current.runSimulation(nodes, []));
  act(() => FakeSocket.instances[0].onclose?.());
  expect(result.current.error).toContain("before simulation finished");
});
