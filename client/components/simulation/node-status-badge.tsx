"use client";
import { useSimulationStore } from "@/stores/simulation-store";
import { getNodeHealth } from "@/lib/simulation/node-health";
const styles = {
  idle: "bg-slate-400",
  healthy: "bg-emerald-500",
  busy: "bg-amber-500",
  overloaded: "bg-red-500",
};
export function NodeStatusBadge({ nodeId }: { nodeId: string }) {
  const latest = useSimulationStore((state) => state.snapshots.at(-1));
  const health = getNodeHealth(nodeId, latest);
  return (
    <span
      title={`Status: ${health}`}
      aria-label={`Node status: ${health}`}
      className={`inline-block size-2.5 shrink-0 rounded-full ${styles[health]}`}
    />
  );
}
