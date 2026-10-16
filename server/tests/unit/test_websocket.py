import json
from dataclasses import asdict
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1.websocket import manager
from app.main import app
from app.infrastructure.redis import get_redis
from app.db.session import get_db
from app.simulation.engine import SimulationEngine
from app.schemas.component import ArchitectureGraph
from app.simulation.state import SimulationConfig
from app.simulation.metrics.collector import MetricsCollector


@pytest.fixture(autouse=True)
def stream_dependencies(monkeypatch):
    redis = AsyncMock()
    redis.getdel.return_value = str(uuid4()).encode()
    redis.eval.return_value = 1
    db = AsyncMock()
    db.get.return_value = SimpleNamespace()
    async def redis_dependency():
        yield redis
    async def db_dependency():
        yield db
    app.dependency_overrides[get_redis] = redis_dependency
    app.dependency_overrides[get_db] = db_dependency
    def enqueue(function, run_id, user_id, graph, duration, interval, seed, maximum, **kwargs):
        engine = SimulationEngine(ArchitectureGraph.model_validate(graph),SimulationConfig(duration_seconds=duration,seed=seed,max_requests=maximum))
        collector = MetricsCollector(engine)
        engine.start()
        events = [{"type":"simulation.started","data":{"duration_seconds":duration,"sample_interval":interval}}]
        sample = 1
        while engine.env.now < duration:
            engine.advance(min(sample*interval,duration))
            events.append({"type":"simulation.metrics","data":asdict(collector.capture())})
            sample += 1
        events.append({"type":"simulation.completed","data":asdict(engine.finalize())})
        redis.xread.return_value = [(b"stream",[(str(i).encode(),{b"event":json.dumps(event).encode()}) for i,event in enumerate(events)])]
    monkeypatch.setattr("app.api.v1.websocket.get_queue",lambda:SimpleNamespace(enqueue=enqueue))
    yield
    app.dependency_overrides.clear()


def payload():
    return {
        "duration_seconds": 5, "sample_interval": 1, "seed": 42,
        "graph": {
            "nodes": [
                {"id": "client", "type": "client", "data": {"rps": 20}},
                {"id": "api", "type": "service", "data": {"latency_ms": 20}},
                {"id": "database", "type": "database", "data": {"pool_size": 5}},
            ],
            "edges": [{"id": "e1", "source": "client", "target": "api"},
                      {"id": "e2", "source": "api", "target": "database"}],
        },
    }


def events_for(data):
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/simulations/stream",headers={"Origin":"http://localhost:3000"}) as ws:
            ws.send_json({"ticket":"single-use-test-ticket"})
            assert ws.receive_json()["type"] == "auth.authenticated"
            ws.send_json(data)
            events = []
            while True:
                event = ws.receive_json()
                events.append(event)
                if event["type"] in {"simulation.completed", "simulation.error"}:
                    break
    assert not manager.connections
    return events


def test_stream_event_sequence():
    events = events_for(payload())
    assert [event["type"] for event in events] == (
        ["simulation.started"] + ["simulation.metrics"] * 5 + ["simulation.completed"]
    )
    snapshots = [event["data"] for event in events[1:-1]]
    assert [snapshot["timestamp"] for snapshot in snapshots] == [1, 2, 3, 4, 5]
    assert snapshots[-1]["completed"] == events[-1]["data"]["completed"]
    assert snapshots[0]["throughput_rps"] > 0


def test_stream_reports_queue_and_background_jobs():
    data = payload()
    data["graph"]["nodes"] += [
        {"id": "queue", "type": "queue"},
        {"id": "worker", "type": "worker", "data": {"processing_ms": 100}},
    ]
    data["graph"]["edges"] = [
        {"id": str(i), "source": a, "target": b}
        for i, (a, b) in enumerate([
            ("client", "api"), ("api", "queue"), ("queue", "worker"), ("worker", "database"),
        ])
    ]
    events = events_for(data)
    snapshot = events[-2]["data"]
    final = events[-1]["data"]
    assert snapshot["job_metrics"]["completed"] > 0
    assert snapshot["queue_depths"]["queue"] > 0
    assert final["completed"] > final["job_metrics"]["completed"]
    assert snapshot["job_metrics"]["completed"] == final["job_metrics"]["completed"]


@pytest.mark.parametrize("change", [
    {"duration_seconds": 0}, {"duration_seconds": 301},
    {"sample_interval": 0}, {"max_requests": 10001}, {"graph": {}},
])
def test_invalid_stream_input(change):
    data = payload()
    data.update(change)
    events = events_for(data)
    assert [event["type"] for event in events] == ["simulation.error"]


def test_nondivisible_sample_interval_includes_final_snapshot():
    data = payload()
    data.update(duration_seconds=2.5, sample_interval=1)
    events = events_for(data)
    assert [e["data"]["timestamp"] for e in events[1:-1]] == [1, 2, 2.5]


def test_websocket_untrusted_origin_rejected():
    from starlette.websockets import WebSocketDisconnect
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/api/v1/simulations/stream",headers={"Origin":"https://evil.example"}):
                pass
