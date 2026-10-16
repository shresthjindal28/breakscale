from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.simulation import SimulationCreate, SimulationResponse, SimulationResultResponse
from app.services.simulation_service import SimulationService

router = APIRouter(prefix="/simulations", tags=["Simulations"])


def get_dev_owner_id() -> UUID:
    settings = get_settings()
    if not settings.DEBUG:
        raise HTTPException(status_code=403, detail="Development authentication is disabled")
    return settings.DEV_USER_ID


@router.post("", response_model=SimulationResponse, status_code=201)
async def create_simulation(
    data: SimulationCreate, db: AsyncSession = Depends(get_db),
    owner_id: UUID = Depends(get_dev_owner_id),
):
    return await SimulationService(db).create(owner_id, data)


@router.get("", response_model=list[SimulationResponse])
async def list_simulations(
    workspace_id: UUID, db: AsyncSession = Depends(get_db),
    owner_id: UUID = Depends(get_dev_owner_id),
):
    return await SimulationService(db).list(workspace_id, owner_id)


@router.get("/{simulation_id}", response_model=SimulationResponse)
async def get_simulation(
    simulation_id: UUID, db: AsyncSession = Depends(get_db),
    owner_id: UUID = Depends(get_dev_owner_id),
):
    return await SimulationService(db).get(simulation_id, owner_id)


@router.get("/{simulation_id}/results", response_model=SimulationResultResponse)
async def get_simulation_result(
    simulation_id: UUID, db: AsyncSession = Depends(get_db),
    owner_id: UUID = Depends(get_dev_owner_id),
):
    return await SimulationService(db).get_result(simulation_id, owner_id)
