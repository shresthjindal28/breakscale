from dataclasses import asdict, dataclass
from typing import Literal

TraceEventType = Literal[
    "request.enter", "request.exit", "request.failed", "request.completed",
]


@dataclass(frozen=True)
class TraceEvent:
    timestamp: float
    request_id: str
    node_id: str
    event_type: TraceEventType


class TraceCollector:
    def __init__(self, max_events: int = 20_000):
        if max_events <= 0:
            raise ValueError("max_events must be positive")
        self.max_events = max_events
        self.events: list[TraceEvent] = []
        self.dropped_events = 0

    def record(self, timestamp: float, request_id: str | int, node_id: str, event_type: TraceEventType):
        if len(self.events) >= self.max_events:
            self.dropped_events += 1
            return
        self.events.append(TraceEvent(float(timestamp), str(request_id), node_id, event_type))

    def export(self) -> dict:
        return {
            "events": [asdict(event) for event in sorted(self.events, key=lambda event: event.timestamp)],
            "dropped_events": self.dropped_events,
            "truncated": self.dropped_events > 0,
        }
