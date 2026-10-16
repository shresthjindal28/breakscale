import random

import pytest
import simpy

from app.schemas.component import ArchitectureGraph
from app.simulation.algorithms.retries import backoff_with_jitter, exponential_backoff
from app.simulation.components.base import SimulatedComponent
from app.simulation.engine import SimulationEngine
from app.simulation.state import ComponentConfig, SimulationConfig


def test_exponential_backoff():
    assert [exponential_backoff(i, 0.5) for i in (1, 2, 3)] == [0.5, 1, 2]


def test_backoff_maximum():
    assert exponential_backoff(10, 1, 5) == 5


def test_jitter_is_deterministic():
    assert backoff_with_jitter(2, random.Random(42)) == backoff_with_jitter(2, random.Random(42))


def test_jitter_bounds_and_spread():
    rng = random.Random(42)
    delays = [backoff_with_jitter(1, rng, jitter=0.2) for _ in range(20)]
    assert all(0.4 <= value <= 0.6 for value in delays)
    assert len(set(delays)) > 1


def retry_engine(data, duration=2, max_requests=1, background=False):
    nodes = [{"id": "client", "type": "client", "data": {"rps": 10}}]
    route = ["client"]
    if background:
        nodes += [{"id": "queue", "type": "queue"},
                  {"id": "worker", "type": "worker", "data": {"processing_ms": 0}}]
        route += ["queue", "worker"]
    nodes.append({"id": "database", "type": "database", "data": data})
    route.append("database")
    return SimulationEngine(ArchitectureGraph.model_validate({
        "nodes": nodes,
        "edges": [{"id": str(i), "source": a, "target": b}
                  for i, (a, b) in enumerate(zip(route, route[1:]))],
    }), SimulationConfig(duration_seconds=duration, max_requests=max_requests))


def outage_data(**overrides):
    return {"failure_start_at": 0, "failure_duration": 10, "max_retries": 2,
            "retry_base_delay": 0.01, "retry_jitter": 0, **overrides}


def test_retries_increase_component_attempts():
    engine = retry_engine(outage_data(), max_requests=20)
    result = engine.run()
    assert result.failed == result.generated == 20
    assert result.component_attempts == 60
    assert result.total_retries == 40
    assert result.retry_amplification == 3
    assert all(r.attempts == 3 and r.retries == 2 for r in engine.requests)


def test_retry_recovers_without_incrementing_http_failure():
    engine = retry_engine(outage_data(failure_duration=0.005))
    result = engine.run()
    assert result.completed == 1 and result.failed == 0
    assert result.total_retries == 1
    assert result.latencies_ms == pytest.approx([20])


def test_pending_retry_does_not_inflate_amplification():
    result = retry_engine(outage_data(retry_base_delay=5)).run()
    assert result.component_attempts == 1
    assert result.total_retries == 0
    assert result.retry_amplification == 1


@pytest.mark.parametrize("cancel", [False, True])
def test_timeout_cancellation_and_late_completion(cancel):
    engine = retry_engine({"latency_ms": 100, "timeout_ms": 10,
                           "cancel_on_timeout": cancel, "circuit_breaker_enabled": True,
                           "failure_threshold": 1})
    result = engine.run()
    metrics = result.node_metrics["database"]
    assert result.failed == 1
    assert metrics["processed"] == (0 if cancel else 1)
    assert metrics["active"] == metrics["queued"] == 0
    assert metrics["circuit_state"] == "open"
    assert metrics["timeouts"] == 1


def test_cancelling_waiting_request_removes_it_from_resource_queue():
    env = simpy.Environment()
    component = SimulatedComponent(env, "service", ComponentConfig(latency_ms=1000))
    active = env.process(component.process())
    waiting = env.process(component.process())

    def cancel():
        yield env.timeout(0.1)
        waiting.interrupt("timeout")

    env.process(cancel())
    env.run(until=0.2)
    assert waiting.value is False
    assert len(component.resource.queue) == 0
    assert component.resource.count == 1
    env.run()
    assert active.value is True


def test_background_component_retries_are_separate_from_worker_attempts():
    engine = retry_engine(outage_data(failure_duration=0.005), background=True)
    result = engine.run()
    assert result.completed == result.job_metrics.completed == 1
    assert result.total_retries == 1
    assert result.job_metrics.failed_attempts == 0
    assert engine.requests[0].attempts == 0
    assert engine.messages[0].attempts == 1


@pytest.mark.parametrize("data", [{"max_retries": -1}, {"max_retries": 11},
    {"retry_base_delay": 0}, {"retry_max_delay": -1}, {"retry_jitter": 2}])
def test_invalid_retry_configuration(data):
    with pytest.raises(ValueError):
        retry_engine(data)
