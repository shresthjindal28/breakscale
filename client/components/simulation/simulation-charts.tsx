"use client";
import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useSimulationStore } from "@/stores/simulation-store";
import type { MetricsSnapshot } from "@/types/simulation";
const charts = [
  { title: "Throughput", dataKey: "throughput", unit: "RPS", color: "#10b981" },
  { title: "P95 Latency", dataKey: "p95", unit: "ms", color: "#818cf8" },
  { title: "Error Rate", dataKey: "errorRate", unit: "%", color: "#f87171" },
  {
    title: "Queue Depth",
    dataKey: "queueDepth",
    unit: "jobs",
    color: "#f59e0b",
  },
];
export function chartData(snapshots: MetricsSnapshot[]) {
  return snapshots.map((snapshot) => ({
    time: snapshot.timestamp,
    throughput: snapshot.throughput_rps,
    p95: snapshot.latency.p95_ms,
    errorRate: snapshot.error_rate * 100,
    queueDepth: Object.values(snapshot.queue_depths).reduce(
      (sum, depth) => sum + depth,
      0,
    ),
  }));
}
export function SimulationCharts() {
  const snapshots = useSimulationStore((state) => state.snapshots);
  const data = useMemo(() => chartData(snapshots), [snapshots]);
  if (!data.length)
    return (
      <div className="rounded-xl border p-8 text-center text-sm text-muted-foreground">
        Run a simulation to view live charts.
      </div>
    );
  return (
    <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-2">
      {charts.map((config) => (
        <section
          key={config.dataKey}
          className="min-w-0 rounded-xl border bg-card p-4"
          aria-label={`${config.title} chart`}
        >
          <h3 className="mb-4 text-sm font-semibold">{config.title}</h3>
          <div className="h-56 w-full min-w-0">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                <XAxis
                  dataKey="time"
                  type="number"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={(value: number) => `${value}s`}
                  fontSize={11}
                />
                <YAxis fontSize={11} width={45} />
                <Tooltip
                  formatter={(value) => [
                    `${Number(value ?? 0).toFixed(2)} ${config.unit}`,
                    config.title,
                  ]}
                  labelFormatter={(label) => `${label}s`}
                />
                <Line
                  type="monotone"
                  dataKey={config.dataKey}
                  stroke={config.color}
                  strokeWidth={2}
                  dot={data.length === 1}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      ))}
    </div>
  );
}
