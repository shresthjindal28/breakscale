import pytest
import simpy

from app.simulation.algorithms.retries import exponential_backoff
from app.simulation.components.queue import MessageQueue
from app.simulation.components.worker import BackgroundWorker
from app.simulation.state import MessageStatus, QueueMessage


def make_message(id: int):
    return QueueMessage(id=id, request_id=id, created_at=0)


def test_queue_capacity():
    env = simpy.Environment()
    queue = MessageQueue(env, "jobs", capacity=2)
    assert queue.publish(make_message(1))
    assert queue.publish(make_message(2))
    assert not queue.publish(make_message(3))
    assert queue.depth == 2
    assert queue.rejected == 1


def test_worker_acknowledges_messages_in_fifo_order():
    env = simpy.Environment()
    queue = MessageQueue(env, "jobs")
    worker = BackgroundWorker(env, "worker-1", queue, processing_ms=100)
    first, second = make_message(1), make_message(2)
    queue.publish(first)
    queue.publish(second)
    env.process(worker.run())
    env.run(until=0.15)
    assert first.status == MessageStatus.ACKNOWLEDGED
    assert second.status == MessageStatus.PROCESSING
    env.run(until=1)
    assert queue.acknowledged == worker.processed == 2
    assert queue.consumed == 2
    assert queue.depth == 0


def test_failed_jobs_retry_then_dead_letter():
    env = simpy.Environment()
    queue = MessageQueue(env, "jobs")
    worker = BackgroundWorker(env, "worker", queue, failure_rate=1, max_attempts=3)
    message = make_message(1)
    queue.publish(message)
    env.process(worker.run())
    env.run(until=3)
    assert message.attempts == worker.failed_attempts == 3
    assert queue.dead_lettered == 1
    assert queue.dead_letters == [message]
    assert message.status == MessageStatus.DEAD_LETTERED
    assert queue.acknowledged == 0


def test_retry_delay_does_not_block_other_messages():
    env = simpy.Environment()
    queue = MessageQueue(env, "jobs")
    worker = BackgroundWorker(env, "worker", queue, failure_rate=1)
    first, second = make_message(1), make_message(2)
    queue.publish(first)
    queue.publish(second)
    env.process(worker.run())
    env.run(until=0.3)
    assert first.attempts == second.attempts == 1
    assert worker.failed_attempts == 2


def test_retry_rejected_by_full_queue_is_dead_lettered():
    env = simpy.Environment()
    queue = MessageQueue(env, "jobs", capacity=1)
    worker = BackgroundWorker(env, "worker", queue)
    message = make_message(1)
    message.attempts = 1
    queue.publish(make_message(2))
    env.process(worker._retry(message))
    env.run()
    assert queue.depth == 1
    assert queue.rejected == queue.dead_lettered == 1
    assert message.status == MessageStatus.DEAD_LETTERED


def test_exponential_backoff_schedule_and_cap():
    assert [exponential_backoff(i) for i in range(1, 6)] == [0.5, 1, 2, 4, 8]
    assert exponential_backoff(10) == 30


@pytest.mark.parametrize("kwargs", [{"attempt": 0}, {"attempt": 1, "base_delay": 0}, {"attempt": 1, "max_delay": -1}])
def test_invalid_retry_settings(kwargs):
    with pytest.raises(ValueError):
        exponential_backoff(**kwargs)


@pytest.mark.parametrize("kwargs", [{"processing_ms": -1}, {"failure_rate": 1.1}, {"max_attempts": 0}])
def test_invalid_worker_settings(kwargs):
    env = simpy.Environment()
    with pytest.raises(ValueError):
        BackgroundWorker(env, "worker", MessageQueue(env, "jobs"), **kwargs)


def test_invalid_queue_capacity():
    with pytest.raises(ValueError):
        MessageQueue(simpy.Environment(), "jobs", capacity=0)


def background_engine(database_data=None, worker_data=None, duration=2, nested_queue=False):
    from app.schemas.component import ArchitectureGraph
    from app.simulation.engine import SimulationEngine
    from app.simulation.state import SimulationConfig

    architecture = ArchitectureGraph.model_validate({
        "nodes": [
            {"id": "client", "type": "client", "data": {"rps": 10}},
            {"id": "api", "type": "service", "data": {"capacity_rps": 100}},
            {"id": "queue", "type": "queue", "data": {"queue_capacity": 100}},
            {"id": "worker", "type": "worker", "data": worker_data or {"processing_ms": 50}},
            {"id": "database", "type": "queue" if nested_queue else "database",
             "data": database_data or {"capacity_rps": 100, "pool_size": 5}},
        ],
        "edges": [
            {"id": str(i), "source": source, "target": target}
            for i, (source, target) in enumerate([
                ("client", "api"), ("api", "queue"),
                ("queue", "worker"), ("worker", "database"),
            ])
        ],
    })
    return SimulationEngine(architecture, SimulationConfig(duration_seconds=duration, max_requests=1))


def test_worker_processes_downstream_database():
    engine = background_engine()
    result = engine.run()
    assert result.completed == result.job_metrics.submitted == result.job_metrics.completed == 1
    assert result.node_metrics["database"]["processed"] == 1
    assert result.job_metrics.latencies_ms[0] == pytest.approx(60)
    assert result.latencies_ms == pytest.approx([10])
    assert engine.messages[0].error is None


def test_job_not_acknowledged_before_database_finishes():
    engine = background_engine(database_data={"latency_ms": 500}, duration=0.2)
    result = engine.run()
    assert result.completed == 1
    assert result.job_metrics.completed == 0
    assert result.node_metrics["queue"]["in_flight"] == 1
    assert result.node_metrics["queue"]["depth"] == 0
    assert engine.messages[0].completed_at is None


def test_downstream_rejections_retry_and_dead_letter_without_failing_http():
    engine = background_engine(database_data={"queue_limit": 0}, worker_data={"max_attempts": 2})
    result = engine.run()
    assert result.completed == 1
    assert result.failed == 0
    assert result.job_metrics.completed == 0
    assert result.job_metrics.dead_lettered == 1
    assert result.job_metrics.failed_attempts == 2
    assert result.node_metrics["queue"]["in_flight"] == 0
    assert engine.messages[0].error == "Component rejected job: database"
    assert engine.messages[0].completed_at is not None


def test_downstream_recovers_on_retry_and_clears_error():
    engine = background_engine(database_data={"queue_limit": 0})

    def recover():
        yield engine.env.timeout(0.3)
        engine.components["database"].config.queue_limit = 100

    engine.env.process(recover())
    result = engine.run()
    assert result.job_metrics.failed_attempts == 1
    assert result.job_metrics.completed == 1
    assert engine.messages[0].attempts == 2
    assert engine.messages[0].error is None


def test_nested_queue_is_explicitly_rejected():
    engine = background_engine(nested_queue=True, worker_data={"max_attempts": 1})
    result = engine.run()
    assert result.job_metrics.dead_lettered == 1
    assert engine.messages[0].error == "Nested queues are not supported yet"


def test_worker_without_downstream_acknowledges():
    engine = background_engine()
    engine.graph.remove_edge("worker", "database")
    result = engine.run()
    assert result.job_metrics.completed == 1
    assert result.node_metrics["database"]["processed"] == 0
