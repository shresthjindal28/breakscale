from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceResponse,
)
from app.services.workspace_service import WorkspaceService


router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


def get_dev_user_id() -> UUID:
    return get_settings().DEV_USER_ID


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(
    data: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    owner_id: UUID = Depends(get_dev_user_id),
):
    return await WorkspaceService(db).create(owner_id, data)


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    db: AsyncSession = Depends(get_db),
    owner_id: UUID = Depends(get_dev_user_id),
):
    return await WorkspaceService(db).list(owner_id)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    owner_id: UUID = Depends(get_dev_user_id),
):
    return await WorkspaceService(db).get(workspace_id, owner_id)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: UUID,
    data: WorkspaceUpdate,
    db: AsyncSession = Depends(get_db),
    owner_id: UUID = Depends(get_dev_user_id),
):
    return await WorkspaceService(db).update(
        workspace_id, owner_id, data
    )


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    owner_id: UUID = Depends(get_dev_user_id),
):
    await WorkspaceService(db).delete(workspace_id, owner_id)
    return Response(status_code=204)