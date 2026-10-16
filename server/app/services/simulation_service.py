import asyncio
from copy import deepcopy
from dataclasses import asdict
from uuid import UUID, uuid4

from fastapi import HTTPException
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.simulation_validation import validate_workload
from app.db.models.simulation import Simulation
from app.db.models.simulation_result import SimulationResult
from app.infrastructure.limits import acquire_slot, release_slot
from app.infrastructure.task_queue import enqueue_simulation
from app.repositories.simulation_repository import SimulationRepository
from app.schemas.component import ArchitectureGraph
from app.schemas.simulation import SimulationCreate
from app.services.workspace_service import WorkspaceService
from app.simulation.engine import SimulationEngine
from app.simulation.metrics.latency import latency_summary
from app.simulation.metrics.throughput import calculate_error_rate, calculate_throughput
from app.simulation.state import SimulationConfig


def execute_simulation(graph_data: dict, duration: float, seed: int):
    graph = ArchitectureGraph.model_validate(graph_data)
    engine = SimulationEngine(graph, SimulationConfig(duration_seconds=duration, seed=seed))
    result = engine.run()
    return {"result": asdict(result), "trace": engine.trace.export()}


def summarize_result(result: dict, duration: float) -> dict:
    summary = {key: value for key, value in result.items()
               if key not in {"node_metrics", "latencies_ms", "job_metrics"}}
    summary["duration_seconds"] = duration
    summary["throughput_rps"] = calculate_throughput(result["completed"], duration)
    summary["error_rate"] = calculate_error_rate(result["failed"], result["generated"])
    summary["latency"] = latency_summary(result["latencies_ms"])
    jobs = dict(result["job_metrics"])
    jobs["latency"] = latency_summary(jobs.pop("latencies_ms"))
    summary["job_metrics"] = jobs
    return summary


class SimulationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SimulationRepository(db)
        self.workspaces = WorkspaceService(db)

    async def create(self, owner_id: UUID, data: SimulationCreate):
        workspace = await self.workspaces.get(data.workspace_id, owner_id)
        try:
            validate_workload(workspace.graph_data)
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, str(exc)) from None
        redis = Redis.from_url(get_settings().REDIS_URL, socket_timeout=5, socket_connect_timeout=5)
        run_id = uuid4()
        try:
            await acquire_slot(redis, owner_id, str(run_id))
            simulation = await self.repo.create(Simulation(
                id=run_id, workspace_id=workspace.id, status="pending",
                duration_seconds=data.duration_seconds,
                config={"seed": data.seed, "duration_seconds": data.duration_seconds,
                        "max_requests": get_settings().MAX_REQUESTS},
                graph_snapshot=deepcopy(workspace.graph_data),
            ))
            await self.db.commit()
            try:
                await asyncio.to_thread(enqueue_simulation, str(simulation.id))
            except Exception:
                simulation.status = "failed"
                await self.repo.save_result(SimulationResult(simulation_id=simulation.id,
                    summary={"error":"Unable to enqueue simulation", "error_type":"EnqueueError"}, node_metrics={}))
                await self.db.commit()
                await release_slot(redis,owner_id,str(run_id))
                raise HTTPException(503, {"message":"Simulation queue unavailable", "simulation_id":str(run_id)}) from None
            await self.db.refresh(simulation)
            return simulation
        finally:
            await redis.aclose()

    async def get(self, simulation_id: UUID, owner_id: UUID):
        simulation = await self.repo.get(simulation_id)
        if simulation is None:
            raise HTTPException(status_code=404, detail="Simulation not found")
        await self.workspaces.get(simulation.workspace_id, owner_id)
        return simulation

    async def list(self, workspace_id: UUID, owner_id: UUID):
        await self.workspaces.get(workspace_id, owner_id)
        return await self.repo.list_by_workspace(workspace_id)

    async def delete(self, simulation_id: UUID, owner_id: UUID):
        simulation = await self.get(simulation_id, owner_id)
        if simulation.status in {"pending", "running", "cancelling"}:
            raise HTTPException(status_code=409, detail="Cannot delete an active simulation")
        await self.db.delete(simulation)
        await self.db.commit()

    async def get_result(self, simulation_id: UUID, owner_id: UUID):
        await self.get(simulation_id, owner_id)
        result = await self.repo.get_result(simulation_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Simulation result not available")
        return result

    async def cancel(self, simulation_id: UUID, owner_id: UUID):
        simulation = await self.get(simulation_id, owner_id)
        await self.db.refresh(simulation, with_for_update=True)
        if simulation.status not in {"pending", "running", "cancelling"}:
            raise HTTPException(409, "Simulation is already finished")
        redis = Redis.from_url(get_settings().REDIS_URL, socket_timeout=5, socket_connect_timeout=5)
        try:
            await redis.set(f"breakscale:cancel:{simulation_id}", "1", ex=86400)
            simulation.status = "cancelled" if simulation.status == "pending" else "cancelling"
            await self.db.commit()
            if simulation.status == "cancelled":
                await release_slot(redis, owner_id, str(simulation_id))
            return simulation
        finally:
            await redis.aclose()
