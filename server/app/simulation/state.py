from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RequestStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MessageStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    ACKNOWLEDGED = "acknowledged"
    DEAD_LETTERED = "dead_lettered"


@dataclass
class QueueMessage:
    id: int
    request_id: int
    created_at: float
    attempts: int = 0
    status: MessageStatus = MessageStatus.QUEUED
    payload: dict = field(default_factory=dict)
    completed_at: float | None = None
    error: str | None = None


@dataclass
class BackgroundJobMetrics:
    submitted: int = 0
    completed: int = 0
    dead_lettered: int = 0
    failed_attempts: int = 0
    latencies_ms: list[float] = field(default_factory=list)


# @dataclass
# class SimulationRequest:
#     id: int
#     created_at: float
#     current_node: str
#     status: RequestStatus = RequestStatus.PENDING
#     completed_at: float | None = None
#     error: str | None = None
#     path: list[str] = field(default_factory=list)


@dataclass
class ComponentConfig:
    capacity_rps: float = 100.0
    concurrency: int = 1
    queue_limit: int = 100
    latency_ms: float = 10.0


@dataclass
class SimulationConfig:
    duration_seconds: float = 10.0
    seed: int = 42
    max_requests: int = 100_000
    default_component: ComponentConfig = field(
        default_factory=ComponentConfig
    )


@dataclass
class SimulationResult:
    generated: int = 0
    completed: int = 0
    failed: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    node_metrics: dict[str, dict[str, Any]] = field(
        default_factory=dict
    )
    job_metrics: BackgroundJobMetrics = field(default_factory=BackgroundJobMetrics)

@dataclass
class SimulationRequest:
    id: int
    created_at: float
    current_node: str
    status: RequestStatus = RequestStatus.PENDING
    completed_at: float | None = None
    error: str | None = None
    path: list[str] = field(default_factory=list)

    # Stable cache key shared by requests for the same resource
    cache_key: str = "default"

    # Prevent accidental infinite traversal
    hops: int = 0
