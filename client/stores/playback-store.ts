"use client";
import { create } from "zustand";
import type {
  RequestAnimation,
  SimulationTrace,
} from "@/types/simulation-trace";
interface PlaybackState {
  trace: SimulationTrace | null;
  animations: RequestAnimation[];
  currentTime: number;
  duration: number;
  speed: number;
  playing: boolean;
  load: (
    trace: SimulationTrace,
    animations: RequestAnimation[],
    duration: number,
  ) => void;
  setTime: (time: number) => void;
  setSpeed: (speed: number) => void;
  setPlaying: (playing: boolean) => void;
  reset: () => void;
}
const initial = {
  trace: null,
  animations: [] as RequestAnimation[],
  currentTime: 0,
  duration: 10,
  speed: 1,
  playing: false,
};
export const usePlaybackStore = create<PlaybackState>((set) => ({
  ...initial,
  load: (trace, animations, duration) => {
    if (!Number.isFinite(duration) || duration <= 0)
      throw new Error("Invalid playback duration");
    set({ ...initial, trace, animations, duration });
  },
  setTime: (time) => {
    if (Number.isFinite(time))
      set((state) => ({
        currentTime: Math.max(0, Math.min(state.duration, time)),
      }));
  },
  setSpeed: (speed) => {
    if (Number.isFinite(speed) && speed > 0) set({ speed });
  },
  setPlaying: (playing) =>
    set((state) => ({ playing: playing && state.trace !== null })),
  reset: () => set(initial),
}));
