export type TraceEventType =
  "request.enter" | "request.exit" | "request.failed" | "request.completed";
export interface TraceEvent {
  timestamp: number;
  request_id: string;
  node_id: string;
  event_type: TraceEventType;
}
export interface SimulationTrace {
  events: TraceEvent[];
  dropped_events: number;
  truncated: boolean;
}
export interface RequestAnimation {
  id: string;
  requestId: string;
  source: string;
  target: string;
  startTime: number;
  endTime: number;
}
