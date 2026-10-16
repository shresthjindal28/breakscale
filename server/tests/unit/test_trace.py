import pytest

from app.schemas.component import ArchitectureGraph
from app.simulation.engine import SimulationEngine
from app.simulation.metrics.trace import TraceCollector
from app.simulation.state import SimulationConfig


def test_trace_records_events():
    trace = TraceCollector(max_events=10)
    trace.record(1.0, "req-1", "client", "request.enter")
    trace.record(1.2, "req-1", "api", "request.enter")
    exported = trace.export()
    assert len(exported["events"]) == 2
    assert exported["events"][0]["node_id"] == "client"
    assert exported["truncated"] is False


def test_trace_limit():
    trace = TraceCollector(max_events=2)
    for index in range(5):
        trace.record(index, f"req-{index}", "api", "request.enter")
    assert trace.export()["dropped_events"] == 3
    assert trace.export()["truncated"] is True
    assert len(trace.events) == 2


def test_trace_sorted_by_timestamp_and_stable_at_same_time():
    trace = TraceCollector()
    trace.record(2, "r", "api", "request.exit")
    trace.record(1, "r", "api", "request.enter")
    trace.record(2, "r", "api", "request.completed")
    assert [e["event_type"] for e in trace.export()["events"]] == [
        "request.enter", "request.exit", "request.completed",
    ]


def test_invalid_trace_capacity():
    with pytest.raises(ValueError):
        TraceCollector(0)


def engine_for(data=None, queue=False):
    return SimulationEngine(ArchitectureGraph.model_validate({
        "nodes": [{"id": "client", "type": "client", "data": {"rps": 1}},
                  {"id": "api", "type": "queue" if queue else "service", "data": data or {}}],
        "edges": [{"id": "e", "source": "client", "target": "api"}],
    }), SimulationConfig(duration_seconds=1, max_requests=1))


def test_engine_traces_one_terminal_completion():
    engine = engine_for()
    result = engine.run()
    events = engine.trace.export()["events"]
    assert [e["event_type"] for e in events] == [
        "request.enter", "request.exit", "request.enter", "request.exit", "request.completed",
    ]
    assert events[-1]["timestamp"] == pytest.approx(result.latencies_ms[0] / 1000)
    assert events[-1]["request_id"] == "1"


def test_failed_processing_is_not_traced_as_completed():
    engine = engine_for({"queue_limit": 0})
    engine.run()
    types = [e["event_type"] for e in engine.trace.export()["events"]]
    assert types[-1] == "request.failed"
    assert "request.completed" not in types


def test_queue_acceptance_finishes_http_trace():
    engine = engine_for(queue=True)
    engine.run()
    event = engine.trace.export()["events"][-1]
    assert event["node_id"] == "api"
    assert event["event_type"] == "request.completed"
