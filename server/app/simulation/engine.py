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

        self.graph = GraphBuilder(architecture).build()
        self.components: dict[str, SimulatedComponent] = {}
        self.load_balancers: dict[str, LoadBalancer] = {}
        self.caches: dict[str, LRUCache] = {}
        self.node_data = {node.id: node.data for node in architecture.nodes}

        for node in architecture.nodes:
            if node.type == "client":
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

        return self.result
