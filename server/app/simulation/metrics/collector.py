from dataclasses import asdict, dataclass, field

from app.simulation.metrics.latency import latency_summary
from app.simulation.metrics.throughput import calculate_error_rate, calculate_throughput


@dataclass
class MetricsSnapshot:
    timestamp: float
    generated: int
    completed: int
    failed: int
    throughput_rps: float
    error_rate: float
    latency: dict
    queue_depths: dict[str, int] = field(default_factory=dict)
    component_metrics: dict = field(default_factory=dict)
    job_metrics: dict = field(default_factory=dict)
    total_retries: int = 0
    component_attempts: int = 0
    retry_amplification: float = 1.0


class MetricsCollector:
    def __init__(self, engine):
        self.engine = engine
        self.snapshots: list[MetricsSnapshot] = []

    def capture(self) -> MetricsSnapshot:
        now = float(self.engine.env.now)
        result = self.engine.result
        initial = result.component_attempts - result.total_retries
        jobs = self.engine.collect_job_metrics()
        job_metrics = asdict(jobs)
        job_metrics["latency"] = latency_summary(jobs.latencies_ms)
        snapshot = MetricsSnapshot(
            timestamp=now, generated=result.generated, completed=result.completed,
            failed=result.failed,
            throughput_rps=calculate_throughput(result.completed, now),
            error_rate=calculate_error_rate(result.failed, result.generated),
            latency=latency_summary(result.latencies_ms),
            queue_depths={node_id: queue.depth for node_id, queue in self.engine.queues.items()},
            component_metrics=self.engine.collect_node_metrics(),
            job_metrics=job_metrics, total_retries=result.total_retries,
            component_attempts=result.component_attempts,
            retry_amplification=result.component_attempts / initial if initial > 0 else 1.0,
        )
        self.snapshots.append(snapshot)
        return snapshot
