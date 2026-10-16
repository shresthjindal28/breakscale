from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SimulationCreate(BaseModel):
    workspace_id: UUID
    duration_seconds: float = Field(default=10, gt=0, le=300, allow_inf_nan=False)
    seed: int = 42


class SimulationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    status: str
    duration_seconds: float
    created_at: datetime | None = None


class SimulationResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    simulation_id: UUID
    summary: dict
    node_metrics: dict
