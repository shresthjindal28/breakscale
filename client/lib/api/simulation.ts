import { z } from "zod";
import type { BackendGraph } from "@/lib/simulation/graph-adapter";
import type { SimulationEvent } from "@/types/simulation";
const counts = {
  generated: z.number(),
  completed: z.number(),
  failed: z.number(),
};
const latency = z.object({
  avg_ms: z.number(),
  p50_ms: z.number(),
  p95_ms: z.number(),
  p99_ms: z.number(),
  max_ms: z.number(),
});
const jobs = z.object({
  submitted: z.number(),
  completed: z.number(),
  dead_lettered: z.number(),
  failed_attempts: z.number(),
  latencies_ms: z.array(z.number()),
});
const metrics = z.record(z.record(z.unknown()));
const retries = {
  total_retries: z.number(),
  component_attempts: z.number(),
  retry_amplification: z.number(),
};
const eventSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("simulation.started"),
    data: z.object({
      duration_seconds: z.number(),
      sample_interval: z.number(),
    }),
  }),
  z.object({
    type: z.literal("simulation.metrics"),
    data: z.object({
      ...counts,
      ...retries,
      timestamp: z.number(),
      throughput_rps: z.number(),
      error_rate: z.number(),
      latency,
      queue_depths: z.record(z.number()),
      component_metrics: metrics,
      job_metrics: jobs.extend({ latency }),
    }),
  }),
  z.object({
    type: z.literal("simulation.completed"),
    data: z.object({
      ...counts,
      ...retries,
      latencies_ms: z.array(z.number()),
      node_metrics: metrics,
      job_metrics: jobs,
    }),
  }),
  z.object({
    type: z.literal("simulation.error"),
    data: z.object({ message: z.string() }),
  }),
]);
export function parseSimulationEvent(data: string): SimulationEvent {
  return eventSchema.parse(JSON.parse(data));
}
interface StartSimulationOptions {
  graph: BackendGraph;
  durationSeconds: number;
  sampleInterval?: number;
  seed?: number;
  onEvent: (event: SimulationEvent) => void;
  onError: (error: Error) => void;
  onClose?: () => void;
}
export function connectSimulation(options: StartSimulationOptions): WebSocket {
  const baseUrl =
    process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/api/v1";
  const socket = new WebSocket(
    `${baseUrl.replace(/\/$/, "")}/simulations/stream`,
  );
  socket.onopen = () =>
    socket.send(
      JSON.stringify({
        graph: options.graph,
        duration_seconds: options.durationSeconds,
        sample_interval: options.sampleInterval ?? 0.5,
        seed: options.seed ?? 42,
      }),
    );
  socket.onmessage = (message) => {
    let event: SimulationEvent;
    try {
      event = parseSimulationEvent(message.data as string);
    } catch {
      options.onError(new Error("Invalid simulation event received"));
      socket.close();
      return;
    }
    options.onEvent(event);
  };
  socket.onerror = () =>
    options.onError(
      new Error(
        "WebSocket connection failed. Check that the backend is running.",
      ),
    );
  socket.onclose = () => options.onClose?.();
  return socket;
}
