"use client";

import { useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  ReactFlowProvider,
} from "@xyflow/react";
import { motion, MotionConfig } from "motion/react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { format } from "date-fns";
import { Save, FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { SimulationControls } from "@/components/simulation/simulation-controls";
import { SimulationMetrics } from "@/components/simulation/simulation-metrics";
import { NodeForm } from "@/components/node-form";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { loadWorkspace, saveWorkspace } from "@/lib/storage";

import { SavedSimulations } from "@/components/simulation/saved-simulations";
import { SimulationCharts } from "@/components/simulation/simulation-charts";
import { NodeMetricsPanel } from "@/components/simulation/node-metrics-panel";
import { SimulationNode } from "@/components/simulation/simulation-node";
const nodeTypes = { default: SimulationNode };

export function WorkspacePlayground() {
  const store = useWorkspaceStore();
  const [status, setStatus] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const selectedNode = store.nodes.find((node) => node.id === selectedNodeId);
  const [busy, setBusy] = useState(false);

  async function persist(action: "save" | "load") {
    setBusy(true);
    try {
      if (action === "save") {
        const savedAt = new Date().toISOString();
        await saveWorkspace("playground", {
          version: 1,
          savedAt,
          nodes: store.nodes.map(({ id, position, data }) => ({
            id,
            position,
            data,
          })),
          edges: store.edges.map(({ id, source, target }) => ({
            id,
            source,
            target,
          })),
        });
        setStatus(`Saved at ${format(new Date(savedAt), "HH:mm:ss")}`);
      } else {
        const snapshot = await loadWorkspace("playground");
        if (snapshot) {
          store.restore(snapshot);
          setStatus(
            `Loaded save from ${format(new Date(snapshot.savedAt), "PPp")}`,
          );
        } else setStatus("No saved workspace yet.");
      }
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : "Storage operation failed.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <MotionConfig reducedMotion="user">
      <motion.main
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="mx-auto w-full max-w-6xl space-y-6 p-6"
      >
        <h1 className="text-3xl font-semibold">Workspace playground</h1>
        <p className="text-muted-foreground">
          Choose component types, connect their handles, and run a simulation.
          Save your canvas in this browser.
        </p>
        <div className="grid gap-6 md:grid-cols-[280px_1fr]">
          <div className="space-y-6">
            <NodeMetricsPanel
              nodeId={selectedNode?.id ?? null}
              nodeLabel={selectedNode?.data.label}
            />
            <Card>
              <CardHeader>
                <CardTitle>Add a node</CardTitle>
              </CardHeader>
              <CardContent>
                <NodeForm onAdd={store.addNode} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Canvas totals</CardTitle>
              </CardHeader>
              <CardContent>
                <div
                  className="h-48"
                  role="img"
                  aria-label={`${store.nodes.length} nodes and ${store.edges.length} connections`}
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={[
                        { name: "Nodes", count: store.nodes.length },
                        { name: "Edges", count: store.edges.length },
                      ]}
                    >
                      <XAxis dataKey="name" />
                      <YAxis allowDecimals={false} />
                      <Tooltip />
                      <Bar dataKey="count" fill="var(--chart-1)" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>
          <div className="min-w-0 space-y-4">
            <SimulationControls nodes={store.nodes} edges={store.edges} />
            <div className="h-[500px] overflow-hidden rounded-xl border bg-background">
              <ReactFlowProvider>
                <ReactFlow
                  nodeTypes={nodeTypes}
                  onNodeClick={(_, node) => setSelectedNodeId(node.id)}
                  onPaneClick={() => setSelectedNodeId(null)}
                  nodes={store.nodes}
                  edges={store.edges}
                  onNodesChange={store.onNodesChange}
                  onEdgesChange={store.onEdgesChange}
                  onConnect={store.onConnect}
                  fitView
                >
                  <Background />
                  <Controls />
                  <MiniMap />
                </ReactFlow>
              </ReactFlowProvider>
            </div>
            <SimulationMetrics />
            <SimulationCharts />
            <SavedSimulations />
            <div className="flex flex-wrap gap-3">
              <Button variant="outline" onClick={() => store.loadExample()}>
                Load example architecture
              </Button>
              <Button variant="outline" onClick={() => store.loadExample(true)}>
                Load overload example
              </Button>
              <Button disabled={busy} onClick={() => persist("save")}>
                <Save aria-hidden="true" />
                Save
              </Button>
              <Button
                variant="outline"
                disabled={busy}
                onClick={() => persist("load")}
              >
                <FolderOpen aria-hidden="true" />
                Load
              </Button>
            </div>
            <p role="status" className="text-sm text-muted-foreground">
              {status}
            </p>
          </div>
        </div>
      </motion.main>
    </MotionConfig>
  );
}
