"use client";
import type {
  SavedSimulation,
  SavedSimulationResult,
} from "@/types/simulation-history";
export function formatMetric(value: unknown, unit = ""): string {
  return typeof value === "number" && Number.isFinite(value)
    ? `${value.toFixed(2)}${unit}`
    : "N/A";
}
export function SimulationComparison({
  first,
  second,
  firstRun,
  secondRun,
}: {
  first: SavedSimulationResult;
  second: SavedSimulationResult;
  firstRun?: SavedSimulation;
  secondRun?: SavedSimulation;
}) {
  const a = first.summary,
    b = second.summary;
  const rows = [
    {
      label: "Throughput",
      a: a.throughput_rps,
      b: b.throughput_rps,
      unit: " RPS",
      lower: false,
    },
    {
      label: "P95 Latency",
      a: a.latency?.p95_ms,
      b: b.latency?.p95_ms,
      unit: " ms",
      lower: true,
    },
    {
      label: "P99 Latency",
      a: a.latency?.p99_ms,
      b: b.latency?.p99_ms,
      unit: " ms",
      lower: true,
    },
    {
      label: "Error Rate",
      a: a.error_rate === undefined ? undefined : a.error_rate * 100,
      b: b.error_rate === undefined ? undefined : b.error_rate * 100,
      unit: "%",
      lower: true,
    },
    {
      label: "Total Retries",
      a: a.total_retries,
      b: b.total_retries,
      unit: "",
      lower: true,
    },
    {
      label: "Retry Amplification",
      a: a.retry_amplification,
      b: b.retry_amplification,
      unit: "x",
      lower: true,
    },
  ];
  return (
    <section className="space-y-4 rounded-xl border bg-card p-5">
      <h3 className="text-lg font-semibold">Run Comparison</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left">
              <th className="p-3">Metric</th>
              <th className="p-3">Run A · {first.simulation_id.slice(0, 8)}</th>
              <th className="p-3">
                Run B · {second.simulation_id.slice(0, 8)}
              </th>
              <th className="p-3">Change (B − A)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const difference =
                typeof row.a === "number" &&
                Number.isFinite(row.a) &&
                typeof row.b === "number" &&
                Number.isFinite(row.b)
                  ? row.b - row.a
                  : undefined;
              const improved =
                difference !== undefined &&
                (row.lower ? difference < 0 : difference > 0);
              const worsened =
                difference !== undefined &&
                (row.lower ? difference > 0 : difference < 0);
              return (
                <tr key={row.label} className="border-b last:border-0">
                  <td className="p-3 font-medium">{row.label}</td>
                  <td className="p-3">{formatMetric(row.a, row.unit)}</td>
                  <td className="p-3">{formatMetric(row.b, row.unit)}</td>
                  <td
                    className={`p-3 font-medium ${improved ? "text-emerald-600" : worsened ? "text-red-600" : ""}`}
                  >
                    {difference === undefined
                      ? "N/A"
                      : `${difference > 0 ? "+" : ""}${formatMetric(difference, row.unit)}`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">
        Comparison uses saved metrics. Traffic, duration and seed differences
        can affect results; differences do not imply causation.
      </p>
      <details>
        <summary className="cursor-pointer text-sm font-medium">
          Saved architectures and node metrics
        </summary>
        <div className="mt-3 grid min-w-0 gap-4 md:grid-cols-2">
          {[
            { label: "Run A", run: firstRun, result: first },
            { label: "Run B", run: secondRun, result: second },
          ].map((item) => (
            <div key={item.label} className="min-w-0">
              <h4>
                {item.label} · {item.run?.duration_seconds ?? "N/A"}s
              </h4>
              <pre className="max-h-80 overflow-auto rounded border p-3 text-xs">
                {JSON.stringify(
                  {
                    graph: item.run?.graph_snapshot ?? null,
                    node_metrics: item.result.node_metrics,
                  },
                  null,
                  2,
                )}
              </pre>
            </div>
          ))}
        </div>
      </details>
    </section>
  );
}
