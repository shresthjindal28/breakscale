import type { Edge, Node } from "@xyflow/react";
export const COMPONENT_TYPES = [
  "client",
  "loadBalancer",
  "service",
  "worker",
  "database",
  "cache",
  "queue",
  "cdn",
  "storage",
] as const;
export type ComponentType = (typeof COMPONENT_TYPES)[number];
export interface BackendGraph {
  nodes: {
    id: string;
    type: string;
    data: Record<string, unknown>;
    position: { x: number; y: number };
  }[];
  edges: { id: string; source: string; target: string }[];
}
export function toBackendGraph(nodes: Node[], edges: Edge[]): BackendGraph {
  const backendNodes = nodes.map((node) => {
    const componentType =
      typeof node.data.componentType === "string"
        ? node.data.componentType
        : node.type;
    if (
      !componentType ||
      !COMPONENT_TYPES.some((type) => type === componentType)
    )
      throw new Error(
        `Unsupported component type: ${componentType ?? "undefined"}. Select a component type for each node.`,
      );
    return {
      id: node.id,
      type: componentType,
      data: { ...node.data },
      position: { x: node.position.x, y: node.position.y },
    };
  });
  const ids = new Set(backendNodes.map((node) => node.id));
  if (ids.size !== nodes.length) throw new Error("Duplicate node IDs");
  return {
    nodes: backendNodes,
    edges: edges.map((edge) => {
      if (!ids.has(edge.source) || !ids.has(edge.target))
        throw new Error(`Invalid edge ${edge.id}: missing source or target`);
      return { id: edge.id, source: edge.source, target: edge.target };
    }),
  };
}
