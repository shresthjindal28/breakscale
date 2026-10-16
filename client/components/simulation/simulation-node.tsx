"use client";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { WorkspaceNode } from "@/stores/workspace-store";
import { NodeStatusBadge } from "@/components/simulation/node-status-badge";
export function SimulationNode({
  id,
  data,
  selected,
  isConnectable,
}: NodeProps<WorkspaceNode>) {
  return (
    <div
      className={`min-w-40 rounded-lg border bg-card px-4 py-3 text-card-foreground shadow-sm ${selected ? "border-primary ring-2 ring-primary/30" : "border-border"}`}
    >
      <Handle
        type="target"
        position={Position.Top}
        isConnectable={isConnectable}
      />
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium">{data.label}</span>
        <NodeStatusBadge nodeId={id} />
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {data.componentType ?? "service"}
      </p>
      <Handle
        type="source"
        position={Position.Bottom}
        isConnectable={isConnectable}
      />
    </div>
  );
}
