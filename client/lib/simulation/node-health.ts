import type { MetricsSnapshot } from "@/types/simulation";
export type NodeHealth = "idle" | "healthy" | "busy" | "overloaded";
export function metricNumber(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}
export function getNodeHealth(
  nodeId: string,
  snapshot?: MetricsSnapshot,
): NodeHealth {
  if (!snapshot) return "idle";
  const metrics = snapshot.component_metrics[nodeId];
  const depth = snapshot.queue_depths[nodeId];
  if (depth !== undefined) {
    if (depth > 100 || metricNumber(metrics?.rejected) > 0) return "overloaded";
    return depth > 20 || metricNumber(metrics?.in_flight) > 0
      ? "busy"
      : "healthy";
  }
  if (!metrics) return "idle";
  if (
    metricNumber(metrics.rejected) > 0 ||
    metricNumber(metrics.failures) > 0 ||
    metrics.circuit_state === "open" ||
    metricNumber(metrics.queued) > 10
  )
    return "overloaded";
  if (metricNumber(metrics.queued) > 0 || metricNumber(metrics.active) > 0)
    return "busy";
  return "healthy";
}
