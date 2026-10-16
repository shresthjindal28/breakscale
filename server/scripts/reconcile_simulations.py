"""Recover abandoned runs. Run periodically as a scheduled job."""
import asyncio
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.models.simulation import Simulation
from app.db.models.simulation_result import SimulationResult
from app.db.models.workspace import Workspace
from app.infrastructure.limits import release_slot
from app.infrastructure.task_queue import enqueue_simulation, get_queue


async def reconcile():
    settings=get_settings()
    engine=create_async_engine(settings.database_url,poolclass=NullPool)
    redis=Redis.from_url(settings.redis_url)
    try:
        async with async_sessionmaker(engine,expire_on_commit=False)() as db:
            cutoff=datetime.now(timezone.utc)-timedelta(minutes=16)
            runs=(await db.scalars(select(Simulation).where(Simulation.status.in_(["pending","running","cancelling"]),Simulation.updated_at<cutoff).with_for_update(skip_locked=True))).all()
            for run in runs:
                job=await asyncio.to_thread(get_queue().fetch_job,str(run.id))
                status=str(await asyncio.to_thread(job.get_status)) if job else "missing"
                if status.endswith("STARTED") or status.endswith("started"):
                    continue
                if run.status=="pending" and job is None:
                    try:
                        await asyncio.to_thread(enqueue_simulation,str(run.id))
                        run.updated_at=datetime.now(timezone.utc)
                        continue
                    except Exception:
                        pass
                run.status="cancelled" if run.status=="cancelling" else "failed"
                existing=await db.scalar(select(SimulationResult).where(SimulationResult.simulation_id==run.id))
                if existing is None:
                    db.add(SimulationResult(simulation_id=run.id,summary={"error":"Abandoned simulation reconciled","error_type":"WorkerRecovery"},node_metrics={}))
                owner=await db.scalar(select(Workspace.owner_id).where(Workspace.id==run.workspace_id))
                if owner:
                    await release_slot(redis,owner,str(run.id))
            await db.commit()
            print(f"Reconciled {len(runs)} stale simulations")
    finally:
        await redis.aclose()
        await engine.dispose()
if __name__=="__main__":
    asyncio.run(reconcile())
