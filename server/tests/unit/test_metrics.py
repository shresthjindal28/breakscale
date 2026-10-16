from dataclasses import asdict

import pytest

from app.schemas.component import ArchitectureGraph
from app.simulation.engine import SimulationEngine
from app.simulation.metrics.collector import MetricsCollector
from app.simulation.metrics.latency import latency_summary, percentile
from app.simulation.metrics.throughput import calculate_error_rate, calculate_throughput
from app.simulation.state import SimulationConfig


def test_percentiles():
    values = [10, 20, 30, 40, 50]
    assert percentile(values, 50) == 30
    assert percentile(values, 95) == 48
    assert percentile(values, 99) == 49.6
    assert percentile([7], 99) == 7


def test_empty_latency():
    assert all(value == 0 for value in latency_summary([]).values())


def test_invalid_percentile():
    with pytest.raises(ValueError):
        percentile([], 101)


def test_throughput():
    assert calculate_throughput(100, 10) == 10
    assert calculate_throughput(100, 0) == 0


def test_error_rate():
    assert calculate_error_rate(20, 100) == 0.2
    assert calculate_error_rate(0, 0) == 0


def graph():
    return ArchitectureGraph.model_validate({
        "nodes": [{"id": "client", "type": "client", "data": {"rps": 20}},
                  {"id": "api", "type": "service"}],
        "edges": [{"id": "e", "source": "client", "target": "api"}],
    })


def test_incremental_matches_full_run_and_snapshots_are_independent():
    config = SimulationConfig(duration_seconds=2)
    engine = SimulationEngine(graph(), config)
    collector = MetricsCollector(engine)
    engine.start()
    engine.advance(1)
    first = collector.capture()
    before = asdict(first)
    assert not getattr(engine, "_finalized", False)
    engine.advance(2)
    second = collector.capture()
    assert first.timestamp == 1 and second.timestamp == 2
    assert second.completed > first.completed
    assert asdict(first) == before
    assert asdict(engine.finalize()) == asdict(SimulationEngine(graph(), config).run())
    assert engine.finalize() is engine.result


def test_engine_lifecycle_guards():
    engine = SimulationEngine(graph(), SimulationConfig(duration_seconds=2))
    with pytest.raises(RuntimeError):
        engine.advance(1)
    with pytest.raises(RuntimeError):
        engine.finalize()
    engine.start()
    with pytest.raises(RuntimeError):
        engine.start()
    for until in (0, 3, float("nan")):
        with pytest.raises(ValueError):
            engine.advance(until)
    with pytest.raises(RuntimeError):
        engine.finalize()


def test_invalid_graph_does_not_start_processes():
    engine = SimulationEngine(ArchitectureGraph(nodes=[], edges=[]))
    with pytest.raises(ValueError):
        engine.start()
    assert not getattr(engine, "_started", False)


def test_throughput_uses_interval_including_unequal_samples():
    engine = SimulationEngine(graph(), SimulationConfig(duration_seconds=3, max_requests=10))
    collector = MetricsCollector(engine)
    engine.start()
    engine.advance(1)
    first = collector.capture()
    assert first.throughput_rps == 10
    engine.advance(3)
    second = collector.capture()
    assert second.throughput_rps == 0
    assert second.completed == 10
    assert collector.capture().throughput_rps == 0
