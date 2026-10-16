"use client";
import { create } from "zustand";
import type {
  MetricsSnapshot,
  SimulationResult,
  SimulationStatus,
} from "@/types/simulation";
interface SimulationStore {
  status: SimulationStatus;
  progress: number;
  durationSeconds: number;
  snapshots: MetricsSnapshot[];
  result: SimulationResult | null;
  error: string | null;
  start: (durationSeconds: number) => void;
  setRunning: () => void;
  addSnapshot: (snapshot: MetricsSnapshot) => void;
  complete: (result: SimulationResult) => void;
  fail: (message: string) => void;
  reset: () => void;
}
const initial = {
  status: "idle" as SimulationStatus,
  progress: 0,
  durationSeconds: 10,
  snapshots: [] as MetricsSnapshot[],
  result: null,
  error: null,
};
export const useSimulationStore = create<SimulationStore>((set) => ({
  ...initial,
  start: (durationSeconds) =>
    set({ ...initial, durationSeconds, status: "connecting" }),
  setRunning: () => set({ status: "running" }),
  addSnapshot: (snapshot) =>
    set((state) => ({
      snapshots: [...state.snapshots, snapshot],
      progress: Math.min(
        100,
        (snapshot.timestamp / state.durationSeconds) * 100,
      ),
    })),
  complete: (result) => set({ status: "completed", progress: 100, result }),
  fail: (error) => set({ status: "error", error }),
  reset: () => set(initial),
}));
