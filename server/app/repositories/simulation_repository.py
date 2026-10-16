from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.simulation import Simulation
from app.db.models.simulation_result import SimulationResult


class SimulationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, simulation: Simulation):
        self.db.add(simulation)
        await self.db.flush()
        return simulation

    async def get(self, simulation_id: UUID):
        return await self.db.get(Simulation, simulation_id)

    async def list_by_workspace(self, workspace_id: UUID):
        result = await self.db.execute(
            select(Simulation).where(Simulation.workspace_id == workspace_id)
            .order_by(Simulation.created_at.desc())
        )
        return result.scalars().all()

    async def save_result(self, result: SimulationResult):
        self.db.add(result)
        await self.db.flush()
        return result

    async def get_result(self, simulation_id: UUID):
        result = await self.db.execute(
            select(SimulationResult).where(SimulationResult.simulation_id == simulation_id)
        )
        return result.scalar_one_or_none()
