"use client";

import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import { nanoid } from "nanoid";
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from "@xyflow/react";
import type { WorkspaceSnapshot } from "@/lib/schemas/workspace";

import type { ComponentType } from "@/lib/simulation/graph-adapter";
export type WorkspaceNode = Node<{
  label: string;
  componentType?: ComponentType;
  [key: string]: unknown;
}>;

type WorkspaceState = {
  nodes: WorkspaceNode[];
  edges: Edge[];
  addNode: (label: string, componentType?: ComponentType) => void;
  loadExample: (overloaded?: boolean) => void;
  onNodesChange: (changes: NodeChange<WorkspaceNode>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
  restore: (snapshot: WorkspaceSnapshot) => void;
};

export const useWorkspaceStore = create<WorkspaceState>()(
  immer((set) => ({
    nodes: [
      {
        id: "start",
        position: { x: 100, y: 100 },
        data: { label: "Client", componentType: "client", rps: 20 },
      },
    ],
    edges: [],
    loadExample: (overloaded = false) =>
      set((state) => {
        state.nodes = [
          {
            id: "client",
            position: { x: 100, y: 80 },
            data: {
              label: overloaded ? "Client · 100 RPS" : "Client · 20 RPS",
              componentType: "client",
              rps: overloaded ? 100 : 20,
            },
          },
          {
            id: "api",
            position: { x: 100, y: 240 },
            data: {
              label: overloaded ? "API · 50 RPS" : "API · 100 RPS",
              componentType: "service",
              capacity_rps: overloaded ? 50 : 100,
              queue_limit: overloaded ? 5 : 100,
              latency_ms: 20,
            },
          },
          {
            id: "database",
            position: { x: 100, y: 400 },
            data: {
              label: overloaded ? "Database · 30 RPS" : "Database · 100 RPS",
              componentType: "database",
              capacity_rps: overloaded ? 30 : 100,
              queue_limit: overloaded ? 5 : 100,
              pool_size: overloaded ? 1 : 5,
            },
          },
        ];
        state.edges = [
          { id: "client-api", source: "client", target: "api" },
          { id: "api-database", source: "api", target: "database" },
        ];
      }),
    addNode: (label, componentType = "service") =>
      set((state) => {
        state.nodes.push({
          id: nanoid(),
          position: {
            x: 100 + state.nodes.length * 40,
            y: 100 + state.nodes.length * 80,
          },
          data: { label, componentType },
        });
      }),
    onNodesChange: (changes) =>
      set((state) => {
        state.nodes = applyNodeChanges(changes, state.nodes);
      }),
    onEdgesChange: (changes) =>
      set((state) => {
        state.edges = applyEdgeChanges(changes, state.edges);
      }),
    onConnect: (connection) =>
      set((state) => {
        state.edges = addEdge(connection, state.edges);
      }),
    restore: (snapshot) =>
      set((state) => {
        state.nodes = snapshot.nodes.map((node) => ({
          ...node,
          data: {
            ...node.data,
            componentType: node.data.componentType ?? "service",
          },
        }));
        state.edges = snapshot.edges;
      }),
  })),
);
