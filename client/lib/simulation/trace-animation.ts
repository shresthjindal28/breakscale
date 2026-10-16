import type { RequestAnimation, TraceEvent } from "@/types/simulation-trace";
export function buildRequestAnimations(
  events: TraceEvent[],
  validEdges: Set<string>,
): RequestAnimation[] {
  const grouped = new Map<string, TraceEvent[]>();
  for (const event of events) {
    if (event.event_type !== "request.enter") continue;
    const group = grouped.get(event.request_id) ?? [];
    group.push(event);
    grouped.set(event.request_id, group);
  }
  const animations: RequestAnimation[] = [];
  for (const [requestId, entries] of grouped) {
    entries.sort((a, b) => a.timestamp - b.timestamp);
    for (let index = 1; index < entries.length; index++) {
      const previous = entries[index - 1],
        current = entries[index];
      if (
        previous.node_id === current.node_id ||
        !validEdges.has(`${previous.node_id}->${current.node_id}`) ||
        current.timestamp <= previous.timestamp
      )
        continue;
      animations.push({
        id: `${requestId}-${index}`,
        requestId,
        source: previous.node_id,
        target: current.node_id,
        startTime: previous.timestamp,
        endTime: current.timestamp,
      });
    }
  }
  return animations.sort((a, b) => a.startTime - b.startTime);
}
