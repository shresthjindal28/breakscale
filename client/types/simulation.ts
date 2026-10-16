export type SimulationStatus =
  "idle" | "connecting" | "running" | "completed" | "error";
export interface LatencySummary {
  avg_ms: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  max_ms: number;
}
export interface JobMetrics {
  submitted: number;
  completed: number;
  dead_lettered: number;
  failed_attempts: number;
  latencies_ms: number[];
}
export interface MetricsSnapshot {
  timestamp: number;
  generated: number;
  completed: number;
  failed: number;
  throughput_rps: number;
  error_rate: number;
  latency: LatencySummary;
  queue_depths: Record<string, number>;
  component_metrics: Record<string, Record<string, unknown>>;
  job_metrics: JobMetrics & { latency: LatencySummary };
  total_retries: number;
  component_attempts: number;
  retry_amplification: number;
}
export interface SimulationResult {
  generated: number;
  completed: number;
  failed: number;
  latencies_ms: number[];
  node_metrics: Record<string, Record<string, unknown>>;
  total_retries: number;
  component_attempts: number;
  retry_amplification: number;
  job_metrics: JobMetrics;
}
export type SimulationEvent =
  | {
      type: "simulation.started";
      data: { duration_seconds: number; sample_interval: number };
    }
  | { type: "simulation.metrics"; data: MetricsSnapshot }
  | { type: "simulation.completed"; data: SimulationResult }
  | { type: "simulation.error"; data: { message: string } };
