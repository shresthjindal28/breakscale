from app.schemas.component import ArchitectureGraph
from app.simulation.components.database import DatabaseComponent
from app.simulation.engine import SimulationEngine
from app.simulation.state import SimulationConfig


def make_architecture():
    return ArchitectureGraph.model_validate({
        "nodes": [
            {
                "id": "client-1",
                "type": "client",
                "data": {"rps": 100},
            },
            {
                "id": "service-1",
                "type": "service",
                "data": {
                    "capacity_rps": 50,
                    "concurrency": 1,
                    "queue_limit": 10,
                },
            },
        ],
        "edges": [
            {
                "id": "edge-1",
                "source": "client-1",
                "target": "service-1",
            },
        ],
    })


def test_simulation_generates_requests():
    engine = SimulationEngine(
        make_architecture(),
        SimulationConfig(duration_seconds=2),
    )

    result = engine.run()

    assert result.generated > 0
    assert result.completed > 0


def test_overloaded_service_rejects_requests():
    engine = SimulationEngine(
        make_architecture(),
        SimulationConfig(duration_seconds=2),
    )

    result = engine.run()

    assert result.failed > 0


def test_simulation_is_deterministic():
    config = SimulationConfig(
        duration_seconds=2,
        seed=42,
    )

    first = SimulationEngine(
        make_architecture(),
        config,
    ).run()

    second = SimulationEngine(
        make_architecture(),
        config,
    ).run()

    assert first.generated == second.generated
    assert first.completed == second.completed
    assert first.failed == second.failed
    assert first.latencies_ms == second.latencies_ms


def specialized_engine(kind, data, targets=("a",)):
    nodes = [
        {"id": "client", "type": "client", "data": {"rps": 10}},
        {"id": "middle", "type": kind, "data": data},
        *[{"id": target, "type": "service"} for target in targets],
    ]
    edges = [{"id": "entry", "source": "client", "target": "middle"}]
    edges += [
        {"id": target, "source": "middle", "target": target}
        for target in targets
    ]
    return SimulationEngine(
        ArchitectureGraph.model_validate({"nodes": nodes, "edges": edges}),
        SimulationConfig(duration_seconds=1, max_requests=6),
    )


def test_engine_routes_round_robin():
    engine = specialized_engine("loadBalancer", {"algorithm": "round_robin"}, ("a", "b"))
    result = engine.run()
    assert result.completed == 6
    assert [request.path[-1] for request in engine.requests] == ["a", "b"] * 3


def test_engine_least_connections_uses_active_resources():
    engine = specialized_engine("loadBalancer", {"algorithm": "least_connections"}, ("a", "b"))
    engine.components["a"].resource.request()
    engine.run()
    assert all(request.path[-1] == "b" for request in engine.requests)


def test_engine_cache_hits_skip_downstream_and_report_metrics():
    engine = specialized_engine("cache", {"cache_capacity": 2, "ttl_seconds": 60})
    result = engine.run()
    assert result.completed == 6
    assert result.node_metrics["middle"]["cache_hits"] == 5
    assert result.node_metrics["middle"]["cache_misses"] == 1
    assert result.node_metrics["middle"]["cache_hit_rate"] == 5 / 6
    assert result.node_metrics["a"]["processed"] == 1
    assert engine.requests[0].path == ["client", "middle", "a"]
    assert engine.requests[1].path == ["client", "middle"]


def test_engine_uses_database_connection_pool():
    engine = specialized_engine("database", {"pool_size": 3}, ())
    assert isinstance(engine.components["middle"], DatabaseComponent)
    assert engine.components["middle"].resource.capacity == 3
    assert engine.run().completed == 6


def test_engine_limits_request_hops():
    from app.simulation.state import RequestStatus, SimulationRequest

    engine = specialized_engine("service", {})
    request = SimulationRequest(id=1, created_at=0, current_node="middle", hops=100)
    engine.env.process(engine._request_process(request))
    engine.env.run()
    assert request.status == RequestStatus.FAILED
    assert request.error == "Maximum request hops exceeded"
    assert engine.result.failed == 1


def queue_engine(with_worker=True, capacity=1000):
    nodes = [
        {"id": "client", "type": "client", "data": {"rps": 10}},
        {"id": "jobs", "type": "queue", "data": {"queue_capacity": capacity}},
    ]
    edges = [{"id": "entry", "source": "client", "target": "jobs"}]
    if with_worker:
        nodes += [
            {"id": "worker", "type": "worker", "data": {"processing_ms": 200}},
            {"id": "db", "type": "database"},
        ]
        edges += [
            {"id": "consume", "source": "jobs", "target": "worker"},
            {"id": "write", "source": "worker", "target": "db"},
        ]
    return SimulationEngine(
        ArchitectureGraph.model_validate({"nodes": nodes, "edges": edges}),
        SimulationConfig(duration_seconds=1, max_requests=3),
    )


def test_queue_acceptance_completes_http_and_worker_acknowledges():
    engine = queue_engine()
    result = engine.run()
    assert "jobs" not in engine.components
    assert "worker" not in engine.components
    assert result.completed == 3
    assert result.latencies_ms == [0, 0, 0]
    assert result.node_metrics["jobs"]["acknowledged"] == 3
    assert result.node_metrics["worker"]["processed"] == 3
    assert result.node_metrics["db"]["processed"] == 3
    assert result.job_metrics.submitted == result.job_metrics.completed == 3
    assert result.node_metrics["jobs"]["in_flight"] == 0


def test_full_queue_rejects_http_requests():
    engine = queue_engine(with_worker=False, capacity=1)
    result = engine.run()
    assert result.completed == 1
    assert result.failed == 2
    assert result.node_metrics["jobs"]["depth"] == 1
    assert result.node_metrics["jobs"]["rejected"] == 2


def test_worker_requires_upstream_queue():
    import pytest

    with pytest.raises(ValueError, match="must connect to a queue"):
        specialized_engine("worker", {})
