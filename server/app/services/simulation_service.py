import asyncio
from copy import deepcopy
from dataclasses import asdict
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.simulation import Simulation
from app.db.models.simulation_result import SimulationResult
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
    return asdict(engine.run())


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
        simulation = await self.repo.create(Simulation(
            workspace_id=workspace.id, status="running",
            duration_seconds=data.duration_seconds,
            config={"seed": data.seed, "duration_seconds": data.duration_seconds},
            graph_snapshot=deepcopy(workspace.graph_data),
        ))
        await self.db.commit()
        try:
            result = await asyncio.to_thread(
                execute_simulation, simulation.graph_snapshot, data.duration_seconds, data.seed,
            )
        except Exception as exc:
            simulation.status = "failed"
            await self.repo.save_result(SimulationResult(
                simulation_id=simulation.id,
                summary={"error": str(exc), "error_type": type(exc).__name__},
                node_metrics={},
            ))
            await self.db.commit()
            raise HTTPException(
                status_code=422 if isinstance(exc, (ValueError, TypeError, ZeroDivisionError)) else 500,
                detail={"message": "Simulation failed", "simulation_id": str(simulation.id)},
            ) from exc
        simulation.status = "completed"
        await self.repo.save_result(SimulationResult(
            simulation_id=simulation.id,
            summary=summarize_result(result, data.duration_seconds),
            node_metrics=result["node_metrics"],
        ))
        await self.db.commit()
        await self.db.refresh(simulation)
        return simulation

    async def get(self, simulation_id: UUID, owner_id: UUID):
        simulation = await self.repo.get(simulation_id)
        if simulation is None:
            raise HTTPException(status_code=404, detail="Simulation not found")
        await self.workspaces.get(simulation.workspace_id, owner_id)
        return simulation

    async def list(self, workspace_id: UUID, owner_id: UUID):
        await self.workspaces.get(workspace_id, owner_id)
        return await self.repo.list_by_workspace(workspace_id)

    async def get_result(self, simulation_id: UUID, owner_id: UUID):
        await self.get(simulation_id, owner_id)
        result = await self.repo.get_result(simulation_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Simulation result not available")
        return result
