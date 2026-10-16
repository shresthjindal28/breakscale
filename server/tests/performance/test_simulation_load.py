from app.schemas.component import ArchitectureGraph
from app.simulation.engine import SimulationEngine
from app.simulation.state import SimulationConfig


def test_large_workload_keeps_trace_bounded():
    ids = ["client"] + [f"service-{index}" for index in range(49)]
    graph = ArchitectureGraph.model_validate(
        {
            "nodes": [{"id": ids[0], "type": "client", "data": {"rps": 1000}}]
            + [
                {"id": node, "type": "service", "data": {"capacity_rps": 10000, "latency_ms": 1}}
                for node in ids[1:]
            ],
            "edges": [{"id": str(i), "source": a, "target": b} for i, (a, b) in enumerate(zip(ids, ids[1:]))],
        }
    )
    engine = SimulationEngine(graph, SimulationConfig(duration_seconds=2, max_requests=1000))
    result = engine.run()
    assert result.generated == result.completed == 1000
    assert len(engine.trace.events) == 20000
    assert engine.trace.dropped_events > 0
