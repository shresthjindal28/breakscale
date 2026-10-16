import math
import random
from typing import Any

import networkx as nx

from app.schemas.component import ArchitectureGraph
from app.simulation.algorithms.caching import LRUCache
from app.simulation.algorithms.load_balancing import LoadBalancer
from app.simulation.algorithms.retries import backoff_with_jitter
from app.simulation.components.base import SimulatedComponent
from app.simulation.components.database import DatabaseComponent
from app.simulation.components.queue import MessageQueue
from app.simulation.components.worker import BackgroundWorker
from app.simulation.failures.circuit_breaker import CircuitBreaker
from app.simulation.failures.injector import FailureEvent, FailureInjector
from app.simulation.failures.recovery import RecoveryPolicy
from app.simulation.graph import GraphBuilder
from app.simulation.metrics.trace import TraceCollector
from app.simulation.scheduler import SimulationScheduler
from app.simulation.state import (
    ComponentConfig,
    MessageStatus,
    QueueMessage,
    RequestStatus,
    SimulationConfig,
    SimulationRequest,
    SimulationResult,
)
from app.simulation.validator import GraphValidator


class SimulationEngine:
    def __init__(
        self,
        architecture: ArchitectureGraph,
        config: SimulationConfig | None = None,
    ):
        self.architecture = architecture
        self.config = config or SimulationConfig()
        self.scheduler = SimulationScheduler()
        self.env = self.scheduler.env
        self.failure_injector = FailureInjector(self.env)
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
        self.component_failures: dict[str, int] = {}
        self.component_timeouts: dict[str, int] = {}
        self.random = random.Random(self.config.seed)

        self.result = SimulationResult()
        self.trace = TraceCollector(max_events=20_000)
        self.requests: list[SimulationRequest] = []
        self.messages: list[QueueMessage] = []

        self.graph = GraphBuilder(architecture).build()
        self.components: dict[str, SimulatedComponent] = {}
        self.load_balancers: dict[str, LoadBalancer] = {}
        self.caches: dict[str, LRUCache] = {}
        self.queues: dict[str, MessageQueue] = {}
        self.workers: dict[str, BackgroundWorker] = {}
        self.node_data = {node.id: node.data for node in architecture.nodes}

        for node in architecture.nodes:
            if node.type in {"client", "queue", "worker"}:
                continue

            data = node.data

            component_config = ComponentConfig(
                capacity_rps=float(
                    data.get(
                        "capacity_rps",
                        data.get("capacity", 100),
                    )
                ),
                concurrency=int(data.get("concurrency", 1)),
                queue_limit=int(data.get("queue_limit", 100)),
                latency_ms=float(data.get("latency_ms", 10)),
            )

            component: SimulatedComponent
            if node.type == "database":
                component = DatabaseComponent(
                    self.env, node.id, component_config,
                    pool_size=int(data.get("pool_size", 10)),
                )
            else:
                component = SimulatedComponent(self.env, node.id, component_config)
            self.components[node.id] = component

            if node.type == "loadBalancer":
                self.load_balancers[node.id] = LoadBalancer(
                    algorithm=data.get("algorithm", "round_robin"),
                    seed=self.config.seed,
                )
            if node.type == "cache":
                self.caches[node.id] = LRUCache(
                    capacity=int(data.get("cache_capacity", 1000))
                )

        for node in architecture.nodes:
            if node.id not in self.components:
                continue
            data = node.data
            if data.get("timeout_ms") is not None and float(data["timeout_ms"]) <= 0:
                raise ValueError("timeout_ms must be positive")
            if not 0 <= int(data.get("max_retries", 0)) <= 10:
                raise ValueError("max_retries must be between 0 and 10")
            if float(data.get("retry_base_delay", 0.5)) <= 0 or float(data.get("retry_max_delay", 30)) <= 0:
                raise ValueError("Retry delays must be positive")
            if not 0 <= float(data.get("retry_jitter", 0.2)) <= 1:
                raise ValueError("jitter must be between 0 and 1")
            if data.get("circuit_breaker_enabled", False):
                policy = RecoveryPolicy(
                    failure_threshold=int(data.get("failure_threshold", 5)),
                    recovery_delay_seconds=float(data.get("recovery_timeout", 5.0)),
                )
                self.circuit_breakers[node.id] = CircuitBreaker(
                    failure_threshold=policy.failure_threshold,
                    recovery_timeout=policy.recovery_delay_seconds,
                )
            start, duration = data.get("failure_start_at"), data.get("failure_duration")
            if (start is None) != (duration is None):
                raise ValueError("failure_start_at and failure_duration must be supplied together")
            if start is not None:
                assert duration is not None
                self.failure_injector.schedule(FailureEvent(node.id, float(start), float(duration)))

        for node in architecture.nodes:
            if node.type == "queue":
                self.queues[node.id] = MessageQueue(
                    self.env, node.id,
                    capacity=int(node.data.get("queue_capacity", 1000)),
                )

        for node in architecture.nodes:
            if node.type != "worker":
                continue
            upstream_queues = [
                predecessor for predecessor in self.graph.predecessors(node.id)
                if predecessor in self.queues
            ]
            if not upstream_queues:
                raise ValueError(f"Worker {node.id} must connect to a queue")
            self.workers[node.id] = BackgroundWorker(
                self.env, node.id, self.queues[upstream_queues[0]],
                processing_ms=float(node.data.get("processing_ms", 100)),
                failure_rate=float(node.data.get("failure_rate", 0)),
                max_attempts=int(node.data.get("max_attempts", 3)),
                seed=self.config.seed,
                downstream=self._process_background_job,
            )

    def _execute_component(self, node_id: str):
        component = self.components[node_id]
        breaker = self.circuit_breakers.get(node_id)
        if breaker is not None and not breaker.allow_request(float(self.env.now)):
            self.component_failures[node_id] = self.component_failures.get(node_id, 0) + 1
            return False
        if not self.failure_injector.is_available(node_id):
            if breaker is not None:
                breaker.record_failure(float(self.env.now))
            self.component_failures[node_id] = self.component_failures.get(node_id, 0) + 1
            return False
        timeout_ms = self.node_data[node_id].get("timeout_ms")
        process = self.env.process(component.process())
        if timeout_ms is None:
            success = yield process
        else:
            outcome = yield process | self.env.timeout(float(timeout_ms) / 1000)
            if process in outcome:
                success = outcome[process]
            else:
                success = False
                self.component_timeouts[node_id] = self.component_timeouts.get(node_id, 0) + 1
                if self.node_data[node_id].get("cancel_on_timeout", False) and process.is_alive:
                    process.interrupt("timeout")
                    yield process
        if success:
            if breaker is not None:
                breaker.record_success()
        else:
            self.component_failures[node_id] = self.component_failures.get(node_id, 0) + 1
            if breaker is not None:
                breaker.record_failure(float(self.env.now))
        return success

    def _execute_with_retries(self, node_id: str, request: SimulationRequest | None = None):
        data = self.node_data[node_id]
        for attempt in range(int(data.get("max_retries", 0)) + 1):
            self.result.component_attempts += 1
            if request is not None:
                request.attempts += 1
            if attempt:
                self.result.total_retries += 1
                if request is not None:
                    request.retries += 1
            success = yield self.env.process(self._execute_component(node_id))
            if success:
                return True
            if attempt == int(data.get("max_retries", 0)):
                return False
            delay = backoff_with_jitter(
                attempt + 1, self.random,
                base_delay=float(data.get("retry_base_delay", 0.5)),
                max_delay=float(data.get("retry_max_delay", 30)),
                jitter=float(data.get("retry_jitter", 0.2)),
            )
            yield self.env.timeout(delay)

    def _process_background_job(self, worker_id: str, message: QueueMessage):
        successors = list(self.graph.successors(worker_id))
        if not successors:
            return True
        current_node = self.random.choice(successors)
        visited = 0
        while True:
            visited += 1
            if visited > 100:
                message.error = "Maximum job hops exceeded"
                return False
            if current_node in self.components:
                success = yield self.env.process(self._execute_with_retries(current_node))
                if not success:
                    message.error = f"Component rejected job: {current_node}"
                    return False
            elif current_node in self.queues:
                message.error = "Nested queues are not supported yet"
                return False
            else:
                message.error = f"Unsupported background component: {current_node}"
                return False

            successors = list(self.graph.successors(current_node))
            if not successors:
                return True
            if current_node in self.load_balancers:
                current_node = self.load_balancers[current_node].select(
                    successors,
                    active_counts={
                        target: self.components[target].resource.count
                        if target in self.components else 0
                        for target in successors
                    },
                )
            else:
                current_node = self.random.choice(successors)

    def _request_process(self, request: SimulationRequest):
        current_node = request.current_node

        while True:
            request.hops += 1
            if request.hops > 100:
                request.status = RequestStatus.FAILED
                request.error = "Maximum request hops exceeded"
                self.result.failed += 1
                self.trace.record(self.env.now, request.id, current_node, "request.failed")
                return
            request.current_node = current_node
            request.path.append(current_node)
            self.trace.record(self.env.now, request.id, current_node, "request.enter")

            if current_node in self.queues:
                message = QueueMessage(
                    id=request.id, request_id=request.id,
                    created_at=float(self.env.now),
                )
                if not self.queues[current_node].publish(message):
                    request.status = RequestStatus.FAILED
                    request.error = f"Queue full: {current_node}"
                    self.result.failed += 1
                    self.trace.record(self.env.now, request.id, current_node, "request.failed")
                    return
                self.messages.append(message)
                self.result.job_metrics.submitted += 1
                self.trace.record(self.env.now, request.id, current_node, "request.exit")
                self._complete_request(request)
                return

            if current_node in self.components:
                request.status = RequestStatus.PROCESSING

                success = yield self.env.process(
                    self._execute_with_retries(current_node, request)
                )

                if not success:
                    request.status = RequestStatus.FAILED
                    request.error = (
                        f"Component failed: {current_node}"
                    )
                    self.result.failed += 1
                    self.trace.record(self.env.now, request.id, current_node, "request.failed")
                    return

            self.trace.record(self.env.now, request.id, current_node, "request.exit")
            successors = list(self.graph.successors(current_node))

            if current_node in self.caches:
                data = self.node_data[current_node]
                if self.caches[current_node].access(
                    request.cache_key,
                    now=float(self.env.now),
                    ttl_seconds=float(data.get("ttl_seconds", 60)),
                ):
                    self._complete_request(request)
                    return

            if not successors:
                self._complete_request(request)
                return

            if current_node in self.load_balancers:
                current_node = self.load_balancers[current_node].select(
                    successors,
                    active_counts={
                        target: self.components[target].resource.count
                        if target in self.components else 0
                        for target in successors
                    },
                )
            else:
                current_node = self.random.choice(successors)

    def _complete_request(self, request: SimulationRequest):
        self.trace.record(self.env.now, request.id, request.current_node, "request.completed")
        request.status = RequestStatus.COMPLETED
        request.completed_at = float(self.env.now)
        self.result.completed += 1
        self.result.latencies_ms.append(
            (request.completed_at - request.created_at) * 1000
        )

    def _generate_traffic(self, client_id: str, rps: float):
        if rps <= 0:
            return

        interval = 1.0 / rps

        while self.env.now < self.config.duration_seconds:
            if self.result.generated >= self.config.max_requests:
                return

            request = SimulationRequest(
                id=self.result.generated + 1,
                created_at=float(self.env.now),
                current_node=client_id,
            )

            self.requests.append(request)
            self.result.generated += 1

            self.scheduler.start_process(
                self._request_process(request)
            )

            yield self.env.timeout(interval)

    def start(self):
        if getattr(self, "_started", False):
            raise RuntimeError("Simulation already started")
        if not math.isfinite(self.config.duration_seconds) or self.config.duration_seconds <= 0:
            raise ValueError("Simulation duration must be positive and finite")
        validation = GraphValidator(
            self.architecture
        ).validate()

        if not validation["valid"]:
            raise ValueError(
                f"Invalid architecture: {validation['errors']}"
            )

        if not nx.is_directed_acyclic_graph(self.graph):
            raise ValueError(
                "Cycles are not supported by this engine version"
            )

        self._started = True
        self.failure_injector.start()
        for worker in self.workers.values():
            self.scheduler.start_process(worker.run())

        for node in self.architecture.nodes:
            if node.type == "client":
                rps = float(node.data.get("rps", 100))

                self.scheduler.start_process(
                    self._generate_traffic(node.id, rps)
                )

    def advance(self, until: float):
        if not getattr(self, "_started", False):
            raise RuntimeError("Start simulation first")
        if not math.isfinite(until) or until <= self.env.now:
            raise ValueError("Target time must be finite and greater than current time")
        if until > self.config.duration_seconds:
            raise ValueError("Cannot advance beyond simulation duration")
        self.env.run(until=until)

    def collect_node_metrics(self) -> dict:
        metrics: dict[str, dict[str, Any]] = {}
        for node_id, component in self.components.items():
            metrics[node_id] = {
                "processed": component.processed,
                "rejected": component.rejected,
                "queued": len(component.resource.queue),
                "active": component.resource.count,
                "avg_wait_ms": (
                    component.total_wait_seconds
                    / component.processed * 1000
                    if component.processed else 0
                ),
            }

        for node_id, cache in self.caches.items():
            metrics[node_id].update({
                "cache_hits": cache.hits,
                "cache_misses": cache.misses,
                "cache_hit_rate": cache.hit_rate,
            })

        for queue_id, queue in self.queues.items():
            metrics[queue_id] = {
                "published": queue.published,
                "consumed": queue.consumed,
                "acknowledged": queue.acknowledged,
                "rejected": queue.rejected,
                "dead_lettered": queue.dead_lettered,
                "depth": queue.depth,
                "in_flight": queue.in_flight,
            }
        for worker_id, worker in self.workers.items():
            metrics[worker_id] = {
                "processed": worker.processed,
                "failed_attempts": worker.failed_attempts,
            }

        for node_id in self.components:
            breaker = self.circuit_breakers.get(node_id)
            metrics[node_id].update({
                "failures": self.component_failures.get(node_id, 0),
                "timeouts": self.component_timeouts.get(node_id, 0),
                "outages": self.failure_injector.outage_counts.get(node_id, 0),
                "circuit_state": breaker.state.value if breaker else None,
                "circuit_open_count": breaker.open_count if breaker else 0,
                "circuit_rejections": breaker.rejected if breaker else 0,
            })

        return metrics

    def collect_job_metrics(self):
        from app.simulation.state import BackgroundJobMetrics

        jobs = BackgroundJobMetrics(submitted=self.result.job_metrics.submitted)
        jobs.completed = sum(
            message.status == MessageStatus.ACKNOWLEDGED for message in self.messages
        )
        jobs.dead_lettered = sum(
            message.status == MessageStatus.DEAD_LETTERED for message in self.messages
        )
        jobs.failed_attempts = sum(worker.failed_attempts for worker in self.workers.values())
        jobs.latencies_ms = [
            (message.completed_at - message.created_at) * 1000
            for message in self.messages
            if message.status == MessageStatus.ACKNOWLEDGED and message.completed_at is not None
        ]
        return jobs

    def finalize(self) -> SimulationResult:
        if not getattr(self, "_started", False) or self.env.now < self.config.duration_seconds:
            raise RuntimeError("Simulation is not finished")
        if getattr(self, "_finalized", False):
            return self.result
        self.result.node_metrics = self.collect_node_metrics()
        self.result.job_metrics = self.collect_job_metrics()
        original_attempts = self.result.component_attempts - self.result.total_retries
        self.result.retry_amplification = (
            self.result.component_attempts / original_attempts if original_attempts > 0 else 1.0
        )
        self._finalized = True
        return self.result

    def run(self) -> SimulationResult:
        self.start()
        self.advance(self.config.duration_seconds)
        return self.finalize()
