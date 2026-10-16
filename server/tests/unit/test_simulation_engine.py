from app.schemas.component import ArchitectureGraph
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