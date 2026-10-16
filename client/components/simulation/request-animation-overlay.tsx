"use client";
import { useMemo } from "react";
import { ViewportPortal, useStore } from "@xyflow/react";
import { usePlaybackStore } from "@/stores/playback-store";
export function RequestAnimationOverlay() {
  const currentTime = usePlaybackStore((state) => state.currentTime);
  const animations = usePlaybackStore((state) => state.animations);
  const nodes = useStore((state) => state.nodes);
  const active = useMemo(
    () =>
      animations.filter(
        (animation) =>
          currentTime >= animation.startTime && currentTime < animation.endTime,
      ),
    [animations, currentTime],
  );
  return (
    <ViewportPortal>
      {active.slice(0, 200).map((animation) => {
        const source = nodes.find((node) => node.id === animation.source),
          target = nodes.find((node) => node.id === animation.target);
        if (!source || !target) return null;
        const startX = source.position.x + (source.measured?.width ?? 160) / 2,
          startY = source.position.y + (source.measured?.height ?? 80) / 2;
        const endX = target.position.x + (target.measured?.width ?? 160) / 2,
          endY = target.position.y + (target.measured?.height ?? 80) / 2;
        const progress =
          (currentTime - animation.startTime) /
          (animation.endTime - animation.startTime);
        const x = startX + (endX - startX) * progress,
          y = startY + (endY - startY) * progress;
        return (
          <div
            key={animation.id}
            data-request-marker={animation.requestId}
            aria-hidden="true"
            className="pointer-events-none absolute size-3 rounded-full border border-white bg-emerald-500 shadow-lg shadow-emerald-500/40"
            style={{ transform: `translate(${x - 6}px,${y - 6}px)` }}
          />
        );
      })}
    </ViewportPortal>
  );
}
