from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    graph_data: dict = Field(default_factory=dict)
    schema_version: int = Field(default=1, ge=1)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    graph_data: dict | None = None
    schema_version: int | None = Field(default=None, ge=1)


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    graph_data: dict
    schema_version: int
    created_at: datetime
    updated_at: datetime