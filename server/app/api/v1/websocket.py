import asyncio
import json
import math
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.simulation_validation import validate_workload
from app.db.models.user import User
from app.db.session import get_db
from app.infrastructure.limits import acquire_slot, release_slot
from app.infrastructure.redis import get_redis
from app.infrastructure.task_queue import get_queue
from app.infrastructure.websocket_manager import WebSocketManager
from app.services.websocket_ticket_service import consume_ws_ticket

router = APIRouter(prefix="/simulations", tags=["Simulation Streaming"])
manager = WebSocketManager()

async def receive_payload(websocket: WebSocket):
    raw = await asyncio.wait_for(websocket.receive_text(),timeout=15)
    if len(raw.encode()) > get_settings().MAX_WS_MESSAGE_BYTES:
        raise ValueError("WebSocket message too large")
    payload = json.loads(raw)
    if not isinstance(payload,dict):
        raise ValueError("Payload must be an object")
    return payload

@router.websocket("/stream")
async def stream_simulation(websocket: WebSocket, redis: Redis = Depends(get_redis), db: AsyncSession = Depends(get_db)):
    if websocket.headers.get("origin") not in get_settings().trusted_origins:
        await websocket.close(code=1008)
        return
    await manager.connect(websocket)
    run_id = None
    user_id = None
    disconnect = None
    reader: asyncio.Future | None = None
    try:
        auth = await receive_payload(websocket)
        user_id = await consume_ws_ticket(redis,auth.get("ticket",""))
        if user_id is None or await db.get(User,user_id) is None:
            await websocket.close(code=1008)
            return
        await db.rollback()
        await manager.send(websocket,{"type":"auth.authenticated","data":{}})
        payload = await receive_payload(websocket)
        graph = validate_workload(payload["graph"])
        duration = float(payload.get("duration_seconds",10))
        interval = float(payload.get("sample_interval",1))
        maximum = int(payload.get("max_requests",get_settings().MAX_REQUESTS))
        if not math.isfinite(duration) or not 0 < duration <= 300:
            raise ValueError("duration_seconds must be positive and at most 300")
        if not math.isfinite(interval) or not 0.1 <= interval <= 300:
            raise ValueError("sample_interval must be between 0.1 and 300 seconds")
        if not 1 <= maximum <= get_settings().MAX_REQUESTS:
            raise ValueError("max_requests exceeds simulation quota")
        run_id = str(uuid4())
        await acquire_slot(redis,user_id,run_id)
        def enqueue():
            return get_queue().enqueue("app.simulation.worker_runner.run_live_simulation",run_id,str(user_id),
                graph.model_dump(),duration,interval,int(payload.get("seed",42)),maximum,
                job_id=run_id,job_timeout=600,ttl=900,result_ttl=300)
        await asyncio.to_thread(enqueue)
        stream = f"breakscale:events:{run_id}"
        cursor = "0-0"
        disconnect = asyncio.create_task(websocket.receive())
        while True:
            reader = asyncio.ensure_future(redis.xread({stream:cursor},count=100,block=1000))
            done,_ = await asyncio.wait([reader,disconnect],return_when=asyncio.FIRST_COMPLETED)
            if disconnect in done:
                raise WebSocketDisconnect()
            for _,messages in reader.result():
                for event_id,fields in messages:
                    cursor = event_id
                    event = json.loads(fields[b"event"])
                    await manager.send(websocket,event)
                    if event["type"] in {"simulation.completed","simulation.error"}:
                        await websocket.close(code=1000)
                        return
    except WebSocketDisconnect:
        pass
    except (ValidationError, ValueError, KeyError, TypeError, OverflowError, TimeoutError, HTTPException) as exc:
        message = str(exc.detail) if isinstance(exc,HTTPException) else str(exc)
        await manager.send(websocket,{"type":"simulation.error","data":{"message":message}})
        await websocket.close(code=1008)
    except RedisError:
        await manager.send(websocket,{"type":"simulation.error","data":{"message":"Simulation queue unavailable"}})
        await websocket.close(code=1013)
    finally:
        for task in (reader,disconnect):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(*(task for task in (reader,disconnect) if task is not None), return_exceptions=True)
        if run_id is not None:
            try:
                await redis.set(f"breakscale:cancel:{run_id}","1",ex=900)
                if user_id is not None:
                    await release_slot(redis,user_id,run_id)
            except RedisError:
                pass
        manager.disconnect(websocket)
