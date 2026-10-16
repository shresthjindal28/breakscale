import asyncio
import json
import logging
from dataclasses import asdict
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.simulation_validation import validate_workload
from app.db.models.simulation import Simulation
from app.db.models.simulation_result import SimulationResult
from app.db.models.workspace import Workspace
from app.infrastructure.limits import release_slot
from app.services.simulation_service import summarize_result
from app.simulation.cancellation import CancellationToken, SimulationCancelled
from app.simulation.engine import SimulationEngine
from app.simulation.metrics.collector import MetricsCollector
from app.simulation.state import SimulationConfig

logger = logging.getLogger(__name__)

async def execute_saved_simulation(simulation_id: str):
    settings = get_settings()
    db_engine = create_async_engine(settings.database_url,poolclass=NullPool)
    sessions = async_sessionmaker(db_engine,expire_on_commit=False)
    redis = Redis.from_url(settings.redis_url,socket_timeout=5,socket_connect_timeout=5)
    owner_id = None
    engine = None
    try:
        async with sessions() as db:
            run = await db.scalar(select(Simulation).where(Simulation.id == UUID(simulation_id)).with_for_update())
            if run is None or run.status != "pending":
                return
            owner_id = await db.scalar(select(Workspace.owner_id).where(Workspace.id == run.workspace_id))
            run.status = "running"
            await db.commit()
            try:
                graph = validate_workload(run.graph_snapshot)
                engine = SimulationEngine(graph,SimulationConfig(duration_seconds=run.duration_seconds,
                    seed=int(run.config.get("seed",42)),max_requests=int(run.config.get("max_requests",settings.MAX_REQUESTS))))
                collector = MetricsCollector(engine)
                token = CancellationToken()
                engine.start()
                batch = 0
                while engine.env.now < run.duration_seconds:
                    if await redis.exists(f"breakscale:cancel:{simulation_id}"):
                        token.cancel()
                    token.check()
                    engine.advance(min(engine.env.now+0.25,run.duration_seconds))
                    batch += 1
                    if batch % 2 == 0 or engine.env.now == run.duration_seconds:
                        event = {"type":"simulation.metrics","data":asdict(collector.capture())}
                        encoded = json.dumps(event)
                        await redis.set(f"breakscale:progress:{simulation_id}",encoded,ex=3600)
                        await redis.publish(f"breakscale:progress:{simulation_id}",encoded)
                await db.refresh(run,with_for_update=True)
                # Cancellation wins if it committed before the final status lock.
                if run.status == "cancelling" or await redis.exists(f"breakscale:cancel:{simulation_id}"):
                    raise SimulationCancelled()
                result = asdict(engine.finalize())
                db.add(SimulationResult(simulation_id=run.id,summary=summarize_result(result,run.duration_seconds),
                    node_metrics=result["node_metrics"],trace_data=engine.trace.export()))
                run.status = "completed"
                await db.commit()
            except SimulationCancelled:
                await db.rollback()
                run = await db.get(Simulation,UUID(simulation_id))
                if run is None:
                    return
                run.status = "cancelled"
                if engine is not None:
                    result = asdict(engine.result)
                    result["job_metrics"] = asdict(engine.collect_job_metrics())
                    summary = summarize_result(result,max(float(engine.env.now),0.001))
                    summary["observed_seconds"] = float(engine.env.now)
                    db.add(SimulationResult(simulation_id=run.id,summary=summary,
                        node_metrics=engine.collect_node_metrics(),trace_data=engine.trace.export()))
                await db.commit()
            except Exception as exc:
                await db.rollback()
                run = await db.get(Simulation,UUID(simulation_id))
                if run is not None:
                    run.status = "failed"
                    existing = await db.scalar(select(SimulationResult).where(SimulationResult.simulation_id == run.id))
                    if existing is None:
                        db.add(SimulationResult(simulation_id=run.id,summary={"error":str(exc),"error_type":type(exc).__name__},node_metrics={},trace_data=engine.trace.export() if engine else None))
                    await db.commit()
                logger.exception("Simulation failed",extra={"simulation_id":simulation_id})
            if run is None:
                return
            finished_event = json.dumps({"type":"simulation.finished","data":{"simulation_id":simulation_id,"status":run.status}})
            await redis.set(f"breakscale:progress:{simulation_id}",finished_event,ex=3600)
            await redis.publish(f"breakscale:progress:{simulation_id}",finished_event)
    finally:
        if owner_id is not None:
            try:
                await release_slot(redis,owner_id,simulation_id)
            except Exception:
                logger.warning("Simulation lease will expire",extra={"simulation_id":simulation_id})
        await redis.aclose()
        await db_engine.dispose()

def run_simulation_job(simulation_id: str):
    asyncio.run(execute_saved_simulation(simulation_id))


def run_live_simulation(run_id: str, user_id: str, graph_data: dict, duration: float, interval: float, seed: int, max_requests: int):
    from app.infrastructure.task_queue import get_queue
    redis = get_queue().connection
    key = f"breakscale:events:{run_id}"
    def emit(event):
        redis.xadd(key,{"event":json.dumps(event)},maxlen=4000)
        redis.expire(key,3600)
    try:
        graph = validate_workload(graph_data)
        engine = SimulationEngine(graph,SimulationConfig(duration_seconds=duration,seed=seed,max_requests=max_requests))
        collector = MetricsCollector(engine)
        engine.start()
        emit({"type":"simulation.started","data":{"duration_seconds":duration,"sample_interval":interval}})
        sample = 1
        while engine.env.now < duration:
            if redis.exists(f"breakscale:cancel:{run_id}"):
                raise SimulationCancelled()
            engine.advance(min(sample*interval,duration))
            emit({"type":"simulation.metrics","data":asdict(collector.capture())})
            sample += 1
        emit({"type":"simulation.completed","data":asdict(engine.finalize())})
    except SimulationCancelled:
        emit({"type":"simulation.error","data":{"message":"Simulation cancelled"}})
    except Exception:
        logger.exception("Live simulation failed",extra={"simulation_id":run_id})
        emit({"type":"simulation.error","data":{"message":"Simulation execution failed"}})
    finally:
        redis.zrem(f"breakscale:slots:{user_id}",run_id)
        redis.close()
