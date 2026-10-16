"use client";
import { useSimulationStore } from "@/stores/simulation-store";
const labels: Record<string, string> = {
  processed: "Processed",
  rejected: "Rejected",
  active: "Active requests",
  queued: "Waiting requests",
  avg_wait_ms: "Average wait (ms)",
  failures: "Failures",
  timeouts: "Timeouts",
  outages: "Outages",
  circuit_state: "Circuit state",
  circuit_open_count: "Circuit opens",
  circuit_rejections: "Circuit rejections",
  published: "Published",
  consumed: "Consumed",
  acknowledged: "Acknowledged",
  dead_lettered: "Dead-lettered",
  in_flight: "In flight",
  failed_attempts: "Failed attempts",
  cache_hits: "Cache hits",
  cache_misses: "Cache misses",
  cache_hit_rate: "Cache hit rate",
};
export function NodeMetricsPanel({
  nodeId,
  nodeLabel,
}: {
  nodeId: string | null;
  nodeLabel?: string;
}) {
  const latest = useSimulationStore((state) => state.snapshots.at(-1));
  if (!nodeId)
    return (
      <div className="rounded-xl border p-4 text-sm text-muted-foreground">
        Select a node to inspect its metrics.
      </div>
    );
  const metrics = latest?.component_metrics[nodeId];
  const depth = latest?.queue_depths[nodeId];
  const rows = Object.entries(labels).flatMap(([key, label]) => {
    const value = metrics?.[key];
    return typeof value === "number" || typeof value === "string"
      ? [
          {
            key,
            label,
            value:
              typeof value === "number"
                ? Number(value.toFixed(3)).toLocaleString()
                : value,
          },
        ]
      : [];
  });
  return (
    <section
      className="rounded-xl border bg-card p-4"
      aria-label="Node metrics"
    >
      <h3 className="font-semibold break-words">{nodeLabel ?? nodeId}</h3>
      <p className="mb-4 text-xs text-muted-foreground">Component metrics</p>
      {!rows.length && depth === undefined ? (
        <p className="text-sm text-muted-foreground">
          No metrics available yet.
        </p>
      ) : (
        <dl className="space-y-3 text-sm">
          {rows.map((row) => (
            <div key={row.key} className="flex justify-between gap-3">
              <dt>{row.label}</dt>
              <dd>{row.value}</dd>
            </div>
          ))}
          {depth !== undefined && (
            <div className="flex justify-between">
              <dt>Queue depth</dt>
              <dd>{depth}</dd>
            </div>
          )}
        </dl>
      )}
      <p className="mt-4 text-xs text-muted-foreground">
        Status uses provisional thresholds and cumulative failures; it may
        remain overloaded after recovery.
      </p>
    </section>
  );
}
