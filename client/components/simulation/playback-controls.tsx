"use client";
import { useEffect } from "react";
import { Pause, Play, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePlaybackStore } from "@/stores/playback-store";
export function PlaybackControls() {
  const {
    currentTime,
    duration,
    speed,
    playing,
    setTime,
    setSpeed,
    setPlaying,
  } = usePlaybackStore();
  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    let last: number | null = null;
    const tick = (timestamp: number) => {
      const delta = last === null ? 0 : (timestamp - last) / 1000;
      last = timestamp;
      const state = usePlaybackStore.getState();
      const next = Math.min(
        state.duration,
        state.currentTime + delta * state.speed,
      );
      state.setTime(next);
      if (next >= state.duration) {
        state.setPlaying(false);
        return;
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing]);
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-xl border bg-card p-4">
      <Button
        variant="outline"
        size="icon"
        aria-label={playing ? "Pause replay" : "Play replay"}
        onClick={() => {
          if (currentTime >= duration) setTime(0);
          setPlaying(!playing);
        }}
      >
        {playing ? <Pause className="size-4" /> : <Play className="size-4" />}
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Restart replay"
        onClick={() => {
          setPlaying(false);
          setTime(0);
        }}
      >
        <RotateCcw className="size-4" />
      </Button>
      <div className="min-w-32 flex-1">
        <input
          type="range"
          min={0}
          max={duration}
          step={0.01}
          value={currentTime}
          onChange={(event) => setTime(Number(event.target.value))}
          className="w-full"
          aria-label="Simulation playback time"
        />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{currentTime.toFixed(2)}s</span>
          <span>{duration.toFixed(2)}s</span>
        </div>
      </div>
      <select
        value={speed}
        aria-label="Playback speed"
        onChange={(event) => setSpeed(Number(event.target.value))}
        className="rounded-md border bg-background p-2 text-sm"
      >
        {[0.5, 1, 2, 4].map((value) => (
          <option key={value} value={value}>
            {value}×
          </option>
        ))}
      </select>
    </div>
  );
}
