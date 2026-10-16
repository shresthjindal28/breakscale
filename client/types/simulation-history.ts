import type { BackendGraph } from "@/lib/simulation/graph-adapter";
export interface SavedSimulation {
  id: string;
  workspace_id: string;
  status: "pending" | "running" | "completed" | "failed";
  duration_seconds: number;
  created_at: string | null;
  graph_snapshot: BackendGraph | null;
}
export interface SavedLatencyMetrics {
  avg_ms: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  max_ms: number;
}
export interface SavedSimulationSummary {
  generated?: number;
  completed?: number;
  failed?: number;
  duration_seconds?: number;
  throughput_rps?: number;
  error_rate?: number;
  latency?: SavedLatencyMetrics;
  total_retries?: number;
  component_attempts?: number;
  retry_amplification?: number;
  error?: string;
}
export interface SavedSimulationResult {
  simulation_id: string;
  summary: SavedSimulationSummary;
  node_metrics: Record<string, Record<string, unknown>>;
}
export interface SavedWorkspace {
  id: string;
  name: string;
  graph_data: BackendGraph;
}
