import random

import networkx as nx

from app.schemas.component import ArchitectureGraph
from app.simulation.graph import GraphBuilder
from app.simulation.scheduler import SimulationScheduler
from app.simulation.components.base import SimulatedComponent
from app.simulation.state import (
    ComponentConfig,
    RequestStatus,
    SimulationConfig,
    SimulationRequest,
    SimulationResult,
)
from app.simulation.validator import GraphValidator
from app.simulation.algorithms.load_balancing import LoadBalancer
from app.simulation.algorithms.caching import LRUCache
from app.simulation.components.database import DatabaseComponent
from app.simulation.components.queue import MessageQueue
from app.simulation.components.worker import BackgroundWorker
from app.simulation.state import MessageStatus, QueueMessage

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
        self.random = random.Random(self.config.seed)

        self.result = SimulationResult()
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
                success = yield self.env.process(self.components[current_node].process())
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
                return
            request.current_node = current_node
            request.path.append(current_node)

            if current_node in self.queues:
                message = QueueMessage(
                    id=request.id, request_id=request.id,
                    created_at=float(self.env.now),
                )
                if not self.queues[current_node].publish(message):
                    request.status = RequestStatus.FAILED
                    request.error = f"Queue full: {current_node}"
                    self.result.failed += 1
                    return
                self.messages.append(message)
                self.result.job_metrics.submitted += 1
                self._complete_request(request)
                return

            if current_node in self.components:
                request.status = RequestStatus.PROCESSING

                success = yield self.env.process(
                    self.components[current_node].process()
                )

                if not success:
                    request.status = RequestStatus.FAILED
                    request.error = (
                        f"Queue full at {current_node}"
                    )
                    self.result.failed += 1
                    return

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

    def run(self) -> SimulationResult:
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

        for worker in self.workers.values():
            self.scheduler.start_process(worker.run())

        for node in self.architecture.nodes:
            if node.type == "client":
                rps = float(node.data.get("rps", 100))

                self.scheduler.start_process(
                    self._generate_traffic(node.id, rps)
                )

        self.scheduler.run(
            until=self.config.duration_seconds
        )

        for node_id, component in self.components.items():
            self.result.node_metrics[node_id] = {
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
            self.result.node_metrics[node_id].update({
                "cache_hits": cache.hits,
                "cache_misses": cache.misses,
                "cache_hit_rate": cache.hit_rate,
            })

        for queue_id, queue in self.queues.items():
            self.result.node_metrics[queue_id] = {
                "published": queue.published,
                "consumed": queue.consumed,
                "acknowledged": queue.acknowledged,
                "rejected": queue.rejected,
                "dead_lettered": queue.dead_lettered,
                "depth": queue.depth,
                "in_flight": queue.in_flight,
            }
        for worker_id, worker in self.workers.items():
            self.result.node_metrics[worker_id] = {
                "processed": worker.processed,
                "failed_attempts": worker.failed_attempts,
            }

        jobs = self.result.job_metrics
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
        return self.result
