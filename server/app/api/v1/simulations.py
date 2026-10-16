from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_owner_id
from app.db.session import get_db
from app.schemas.simulation import SimulationCreate, SimulationResponse, SimulationResultResponse
from app.services.simulation_service import SimulationService

router = APIRouter(prefix="/simulations", tags=["Simulations"])


@router.post("", response_model=SimulationResponse, status_code=202)
async def create_simulation(
    data: SimulationCreate, db: AsyncSession = Depends(get_db),
    owner_id: UUID = Depends(get_owner_id),
):
    return await SimulationService(db).create(owner_id, data)


@router.get("", response_model=list[SimulationResponse])
async def list_simulations(
    workspace_id: UUID, db: AsyncSession = Depends(get_db),
    owner_id: UUID = Depends(get_owner_id),
):
    return await SimulationService(db).list(workspace_id, owner_id)


@router.get("/{simulation_id}", response_model=SimulationResponse)
async def get_simulation(
    simulation_id: UUID, db: AsyncSession = Depends(get_db),
    owner_id: UUID = Depends(get_owner_id),
):
    return await SimulationService(db).get(simulation_id, owner_id)


@router.get("/{simulation_id}/results", response_model=SimulationResultResponse)
async def get_simulation_result(
    simulation_id: UUID, db: AsyncSession = Depends(get_db),
    owner_id: UUID = Depends(get_owner_id),
):
    return await SimulationService(db).get_result(simulation_id, owner_id)


@router.delete("/{simulation_id}", status_code=204)
async def delete_simulation(
    simulation_id: UUID, db: AsyncSession = Depends(get_db),
    owner_id: UUID = Depends(get_owner_id),
):
    await SimulationService(db).delete(simulation_id, owner_id)
    return Response(status_code=204)


@router.get("/{simulation_id}/trace")
async def get_simulation_trace(
    simulation_id: UUID, db: AsyncSession = Depends(get_db),
    owner_id: UUID = Depends(get_owner_id),
):
    result = await SimulationService(db).get_result(simulation_id, owner_id)
    return result.trace_data or {"events": [], "dropped_events": 0, "truncated": False}


@router.post("/{simulation_id}/cancel", response_model=SimulationResponse)
async def cancel_simulation(simulation_id: UUID, db: AsyncSession = Depends(get_db), owner_id: UUID = Depends(get_owner_id)):
    return await SimulationService(db).cancel(simulation_id, owner_id)
