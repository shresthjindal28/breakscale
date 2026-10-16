import asyncio
import math
from dataclasses import asdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.infrastructure.websocket_manager import WebSocketManager
from app.schemas.component import ArchitectureGraph
from app.simulation.engine import SimulationEngine
from app.simulation.metrics.collector import MetricsCollector
from app.simulation.state import SimulationConfig

router = APIRouter(prefix="/simulations", tags=["Simulation Streaming"])
manager = WebSocketManager()


@router.websocket("/stream")
async def stream_simulation(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        payload = await websocket.receive_json()
        if not isinstance(payload, dict):
            raise ValueError("Payload must be an object")
        architecture = ArchitectureGraph.model_validate(payload["graph"])
        duration = float(payload.get("duration_seconds", 10))
        interval = float(payload.get("sample_interval", 1))
        max_requests = int(payload.get("max_requests", 10_000))
        if not math.isfinite(duration) or not 0 < duration <= 300:
            raise ValueError("duration_seconds must be positive and at most 300")
        if not math.isfinite(interval) or not 0.1 <= interval <= 300:
            raise ValueError("sample_interval must be between 0.1 and 300 seconds")
        if not 1 <= max_requests <= 10_000:
            raise ValueError("max_requests must be between 1 and 10000")
        engine = SimulationEngine(architecture, SimulationConfig(
            duration_seconds=duration, seed=int(payload.get("seed", 42)),
            max_requests=max_requests,
        ))
        collector = MetricsCollector(engine)
        engine.start()
        await manager.send(websocket, {"type": "simulation.started", "data": {
            "duration_seconds": duration, "sample_interval": interval,
        }})
        sample = 1
        while engine.env.now < duration:
            engine.advance(min(sample * interval, duration))
            await manager.send(websocket, {
                "type": "simulation.metrics", "data": asdict(collector.capture()),
            })
            sample += 1
            await asyncio.sleep(0)
        result = engine.finalize()
        await manager.send(websocket, {
            "type": "simulation.completed", "data": asdict(result),
        })
        await websocket.close(code=1000)
    except WebSocketDisconnect:
        pass
    except (ValidationError, ValueError, KeyError, TypeError, OverflowError, ZeroDivisionError) as exc:
        await manager.send(websocket, {
            "type": "simulation.error", "data": {"message": str(exc)},
        })
        await websocket.close(code=1008)
    finally:
        manager.disconnect(websocket)
