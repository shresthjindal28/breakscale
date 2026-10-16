import pytest
import simpy

from app.schemas.component import ArchitectureGraph
from app.simulation.engine import SimulationEngine
from app.simulation.failures.circuit_breaker import CircuitBreaker, CircuitState
from app.simulation.failures.injector import FailureEvent, FailureInjector
from app.simulation.failures.recovery import RecoveryPolicy
from app.simulation.state import SimulationConfig


def test_circuit_opens_after_threshold():
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=5)
    assert breaker.allow_request(0)
    breaker.record_failure(0)
    assert breaker.state == CircuitState.CLOSED
    breaker.record_failure(1)
    assert breaker.state == CircuitState.OPEN
    assert not breaker.allow_request(2)
    assert breaker.rejected == 1


def test_circuit_recovers_after_successful_probe():
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=5)
    assert breaker.allow_request(0)
    breaker.record_failure(0)
    assert not breaker.allow_request(3)
    assert breaker.allow_request(5)
    assert breaker.state == CircuitState.HALF_OPEN
    assert not breaker.allow_request(5)
    breaker.record_success()
    assert breaker.state == CircuitState.CLOSED
    assert breaker.allow_request(6)


def test_failed_probe_reopens_and_late_success_does_not_close_open_circuit():
    breaker = CircuitBreaker(1, 1)
    breaker.record_failure(0)
    breaker.record_success()
    assert breaker.state == CircuitState.OPEN
    assert breaker.allow_request(1)
    breaker.record_failure(1)
    assert breaker.open_count == 2
    assert not breaker.allow_request(1.5)


def test_success_resets_consecutive_failures():
    breaker = CircuitBreaker(2)
    breaker.record_failure(0)
    breaker.record_success()
    breaker.record_failure(1)
    assert breaker.state == CircuitState.CLOSED


def test_outage_schedule_and_recovery():
    env = simpy.Environment()
    injector = FailureInjector(env)
    injector.schedule(FailureEvent("db", 2, 3))
    injector.start()
    env.run(until=1)
    assert injector.is_available("db")
    env.run(until=3)
    assert not injector.is_available("db")
    env.run(until=6)
    assert injector.is_available("db")
    assert injector.outage_counts == {"db": 1}


def test_overlapping_outages_rejected():
    injector = FailureInjector(simpy.Environment())
    injector.schedule(FailureEvent("db", 2, 3))
    with pytest.raises(ValueError, match="Overlapping"):
        injector.schedule(FailureEvent("db", 4, 3))


@pytest.mark.parametrize("event", [FailureEvent("db", -1, 2), FailureEvent("db", 0, 0)])
def test_invalid_outages(event):
    with pytest.raises(ValueError):
        FailureInjector(simpy.Environment()).schedule(event)


@pytest.mark.parametrize("factory", [
    lambda: CircuitBreaker(0), lambda: CircuitBreaker(recovery_timeout=0),
    lambda: RecoveryPolicy(0), lambda: RecoveryPolicy(failure_threshold=0),
])
def test_invalid_recovery_configuration(factory):
    with pytest.raises(ValueError):
        factory()


def failure_engine(data, background=False, duration=10, max_requests=100):
    nodes = [{"id": "client", "type": "client", "data": {"rps": 10}}]
    route = ["client"]
    if background:
        nodes += [
            {"id": "queue", "type": "queue"},
            {"id": "worker", "type": "worker", "data": {"processing_ms": 0, "max_attempts": 2}},
        ]
        route += ["queue", "worker"]
    nodes.append({"id": "database", "type": "database", "data": data})
    route.append("database")
    return SimulationEngine(ArchitectureGraph.model_validate({
        "nodes": nodes,
        "edges": [{"id": str(i), "source": a, "target": b}
                  for i, (a, b) in enumerate(zip(route, route[1:]))],
    }), SimulationConfig(duration_seconds=duration, max_requests=max_requests))


def test_ten_second_database_outage_and_circuit_recovery():
    engine = failure_engine({
        "failure_start_at": 2, "failure_duration": 3,
        "circuit_breaker_enabled": True, "failure_threshold": 2,
        "recovery_timeout": 1,
    })
    result = engine.run()
    metrics = result.node_metrics["database"]
    assert result.completed > 0 and result.failed > 0
    assert metrics["outages"] == 1
    assert metrics["circuit_open_count"] > 0
    assert metrics["circuit_rejections"] > 0
    assert metrics["circuit_state"] == "closed"
    assert any(r.completed_at and r.completed_at < 2 for r in engine.requests)
    assert any(r.completed_at and r.completed_at > 5 for r in engine.requests)


def test_timeout_keeps_component_busy_without_acknowledging_job():
    engine = failure_engine({"latency_ms": 500, "timeout_ms": 10},
                            background=True, duration=0.2, max_requests=1)
    result = engine.run()
    metrics = result.node_metrics["database"]
    assert result.completed == 1
    assert result.job_metrics.failed_attempts == 1
    assert result.job_metrics.completed == 0
    assert metrics["timeouts"] == metrics["failures"] == 1
    assert metrics["active"] == 1
    assert metrics["processed"] == 0


def test_successful_operation_before_timeout():
    result = failure_engine({"timeout_ms": 100}, max_requests=1).run()
    assert result.completed == 1
    assert result.node_metrics["database"]["timeouts"] == 0


def test_background_outage_retries_and_dead_letters():
    result = failure_engine({"failure_start_at": 0, "failure_duration": 3},
                            background=True, max_requests=1).run()
    assert result.completed == 1 and result.failed == 0
    assert result.job_metrics.dead_lettered == 1
    assert result.job_metrics.failed_attempts == 2
    assert result.node_metrics["database"]["failures"] == 2


@pytest.mark.parametrize("data", [{"timeout_ms": 0}, {"failure_start_at": 1}])
def test_invalid_component_failure_config(data):
    with pytest.raises(ValueError):
        failure_engine(data)
