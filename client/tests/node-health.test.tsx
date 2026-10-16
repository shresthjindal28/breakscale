import { render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { getNodeHealth } from "@/lib/simulation/node-health";
import { chartData } from "@/components/simulation/simulation-charts";
import { NodeMetricsPanel } from "@/components/simulation/node-metrics-panel";
import { useSimulationStore } from "@/stores/simulation-store";
import type { MetricsSnapshot } from "@/types/simulation";

function snapshot(metrics: Record<string, unknown> = {}): MetricsSnapshot {
  return {
    timestamp: 1,
    generated: 10,
    completed: 5,
    failed: 2,
    throughput_rps: 5,
    error_rate: 0.2,
    latency: { avg_ms: 10, p50_ms: 10, p95_ms: 20, p99_ms: 25, max_ms: 30 },
    queue_depths: {},
    component_metrics: { api: metrics },
    total_retries: 0,
    component_attempts: 10,
    retry_amplification: 1,
    job_metrics: {
      submitted: 0,
      completed: 0,
      dead_lettered: 0,
      failed_attempts: 0,
      latencies_ms: [],
      latency: { avg_ms: 0, p50_ms: 0, p95_ms: 0, p99_ms: 0, max_ms: 0 },
    },
  };
}
afterEach(() => useSimulationStore.getState().reset());
test("health uses queued counts and component failures", () => {
  expect(getNodeHealth("api")).toBe("idle");
  expect(getNodeHealth("api", snapshot())).toBe("healthy");
  expect(getNodeHealth("api", snapshot({ queued: 1 }))).toBe("busy");
  expect(getNodeHealth("api", snapshot({ queued: 11 }))).toBe("overloaded");
  expect(getNodeHealth("api", snapshot({ rejected: 1 }))).toBe("overloaded");
  expect(getNodeHealth("api", snapshot({ circuit_state: "open" }))).toBe(
    "overloaded",
  );
});
test("queue health uses depths even when component metrics exist", () => {
  const data = snapshot();
  data.component_metrics.queue = { published: 200 };
  data.queue_depths.queue = 101;
  expect(getNodeHealth("queue", data)).toBe("overloaded");
  data.queue_depths.queue = 21;
  expect(getNodeHealth("queue", data)).toBe("busy");
  data.queue_depths.queue = 0;
  expect(getNodeHealth("queue", data)).toBe("healthy");
});
test("chart data converts fractions and sums queues", () => {
  const data = snapshot();
  data.queue_depths = { a: 3, b: 4 };
  expect(chartData([data])[0]).toMatchObject({
    errorRate: 20,
    queueDepth: 7,
    throughput: 5,
  });
});
test("inspector renders actual waiting count and selection prompt", () => {
  useSimulationStore
    .getState()
    .addSnapshot(snapshot({ processed: 5, queued: 3, active: 1 }));
  const view = render(<NodeMetricsPanel nodeId="api" nodeLabel="API" />);
  expect(
    screen.getByText("Waiting requests").nextElementSibling,
  ).toHaveTextContent("3");
  view.rerender(<NodeMetricsPanel nodeId={null} />);
  expect(
    screen.getByText("Select a node to inspect its metrics."),
  ).toBeInTheDocument();
});
