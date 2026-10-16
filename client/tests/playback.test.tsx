import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { buildRequestAnimations } from "@/lib/simulation/trace-animation";
import { usePlaybackStore } from "@/stores/playback-store";
import { PlaybackControls } from "@/components/simulation/playback-controls";
import type { TraceEvent } from "@/types/simulation-trace";

afterEach(() => {
  usePlaybackStore.getState().reset();
  vi.unstubAllGlobals();
});
test("timeline groups real entries and skips absent, repeated, and zero-duration edges", () => {
  const events: TraceEvent[] = [
    {
      timestamp: 2,
      request_id: "r",
      node_id: "b",
      event_type: "request.enter",
    },
    {
      timestamp: 0,
      request_id: "r",
      node_id: "a",
      event_type: "request.enter",
    },
    {
      timestamp: 3,
      request_id: "r",
      node_id: "b",
      event_type: "request.enter",
    },
    {
      timestamp: 3,
      request_id: "r",
      node_id: "c",
      event_type: "request.enter",
    },
    {
      timestamp: 4,
      request_id: "r",
      node_id: "d",
      event_type: "request.enter",
    },
    {
      timestamp: 5,
      request_id: "r",
      node_id: "d",
      event_type: "request.completed",
    },
  ];
  const original = JSON.stringify(events);
  expect(buildRequestAnimations(events, new Set(["a->b", "b->c"]))).toEqual([
    {
      id: "r-1",
      requestId: "r",
      source: "a",
      target: "b",
      startTime: 0,
      endTime: 2,
    },
  ]);
  expect(JSON.stringify(events)).toBe(original);
});
test("play, pause, seek, speed, restart and cleanup", () => {
  let callback: FrameRequestCallback | null = null;
  const cancel = vi.fn();
  vi.stubGlobal(
    "requestAnimationFrame",
    vi.fn((cb: FrameRequestCallback) => {
      callback = cb;
      return 1;
    }),
  );
  vi.stubGlobal("cancelAnimationFrame", cancel);
  usePlaybackStore
    .getState()
    .load({ events: [], dropped_events: 0, truncated: false }, [], 10);
  const view = render(<PlaybackControls />);
  fireEvent.click(screen.getByLabelText("Play replay"));
  act(() => callback?.(0));
  act(() => callback?.(1000));
  expect(usePlaybackStore.getState().currentTime).toBe(1);
  fireEvent.change(screen.getByLabelText("Playback speed"), {
    target: { value: "2" },
  });
  act(() => callback?.(2000));
  expect(usePlaybackStore.getState().currentTime).toBe(3);
  fireEvent.click(screen.getByLabelText("Pause replay"));
  expect(usePlaybackStore.getState().playing).toBe(false);
  fireEvent.change(screen.getByLabelText("Simulation playback time"), {
    target: { value: "0.5" },
  });
  expect(usePlaybackStore.getState().currentTime).toBe(0.5);
  fireEvent.click(screen.getByLabelText("Restart replay"));
  expect(usePlaybackStore.getState().currentTime).toBe(0);
  view.unmount();
  expect(cancel).toHaveBeenCalled();
});
test("playback store clamps time and resets speed on loading another run", () => {
  const trace = { events: [], dropped_events: 0, truncated: false };
  usePlaybackStore.getState().load(trace, [], 5);
  usePlaybackStore.getState().setTime(8);
  expect(usePlaybackStore.getState().currentTime).toBe(5);
  usePlaybackStore.getState().setSpeed(4);
  usePlaybackStore.getState().load(trace, [], 10);
  expect(usePlaybackStore.getState().speed).toBe(1);
  expect(usePlaybackStore.getState().playing).toBe(false);
});
