"use client";
import { useSimulationStore } from "@/stores/simulation-store";
function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  );
}
export function SimulationMetrics() {
  const { status, snapshots, error } = useSimulationStore();
  const latest = snapshots.at(-1);
  if (status === "idle")
    return (
      <p className="text-sm text-muted-foreground">
        Run a simulation to view metrics.
      </p>
    );
  if (status === "error")
    return (
      <p role="alert" className="text-sm text-destructive">
        {error}
      </p>
    );
  if (!latest)
    return (
      <p className="text-sm text-muted-foreground">
        Waiting for simulation metrics...
      </p>
    );
  return (
    <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
      <MetricCard
        label="Throughput"
        value={`${latest.throughput_rps.toFixed(1)} RPS`}
      />
      <MetricCard
        label="P95 Latency"
        value={`${latest.latency.p95_ms.toFixed(1)} ms`}
      />
      <MetricCard
        label="Error Rate"
        value={`${(latest.error_rate * 100).toFixed(1)}%`}
      />
      <MetricCard
        label="Completed Requests"
        value={latest.completed.toLocaleString()}
      />
    </div>
  );
}
