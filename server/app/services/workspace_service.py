from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.workspace_repository import WorkspaceRepository
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate


class WorkspaceService:
    def __init__(self, db: AsyncSession):
        self.repository = WorkspaceRepository(db)

    async def create(self, owner_id: UUID, data: WorkspaceCreate):
        return await self.repository.create(
            owner_id=owner_id,
            name=data.name,
            graph_data=data.graph_data,
            schema_version=data.schema_version,
        )

    async def list(self, owner_id: UUID):
        return await self.repository.list_by_owner(owner_id)

    async def get(self, workspace_id: UUID, owner_id: UUID):
        workspace = await self.repository.get_by_id(workspace_id, owner_id)

        if workspace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        return workspace

    async def update(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        data: WorkspaceUpdate,
    ):
        workspace = await self.get(workspace_id, owner_id)

        updates = data.model_dump(exclude_unset=True)

        for field, value in updates.items():
            if value is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"{field} cannot be null",
                )
            setattr(workspace, field, value)

        return await self.repository.save(workspace)

    async def delete(self, workspace_id: UUID, owner_id: UUID):
        workspace = await self.get(workspace_id, owner_id)
        await self.repository.delete(workspace)