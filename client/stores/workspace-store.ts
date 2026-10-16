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

export type WorkspaceNode = Node<{ label: string }>;

type WorkspaceState = {
  nodes: WorkspaceNode[];
  edges: Edge[];
  addNode: (label: string) => void;
  onNodesChange: (changes: NodeChange<WorkspaceNode>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
  restore: (snapshot: WorkspaceSnapshot) => void;
};

export const useWorkspaceStore = create<WorkspaceState>()(
  immer((set) => ({
    nodes: [
      { id: "start", position: { x: 100, y: 100 }, data: { label: "Start" } },
    ],
    edges: [],
    addNode: (label) =>
      set((state) => {
        state.nodes.push({
          id: nanoid(),
          position: {
            x: 100 + state.nodes.length * 40,
            y: 100 + state.nodes.length * 80,
          },
          data: { label },
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
        state.nodes = snapshot.nodes;
        state.edges = snapshot.edges;
      }),
  })),
);
