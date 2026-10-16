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

            self.components[node.id] = SimulatedComponent(
                self.env,
                node.id,
                component_config,
            )

    def _request_process(self, request: SimulationRequest):
        current_node = request.current_node

        while True:
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

            if not successors:
                request.status = RequestStatus.COMPLETED
                request.completed_at = float(self.env.now)
                self.result.completed += 1
                self.result.latencies_ms.append(
                    (request.completed_at - request.created_at)
                    * 1000
                )
                return

            current_node = self.random.choice(successors)

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

        return self.result