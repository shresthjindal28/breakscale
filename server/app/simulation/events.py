from dataclasses import dataclass
from enum import Enum


class EventType(str, Enum):
    REQUEST_ARRIVAL = "request_arrival"
    SERVICE_START = "service_start"
    SERVICE_COMPLETE = "service_complete"
    REQUEST_FAILED = "request_failed"
    REQUEST_COMPLETED = "request_completed"


@dataclass(frozen=True)
class SimulationEvent:
    timestamp: float
    event_type: EventType
    request_id: int
    node_id: str