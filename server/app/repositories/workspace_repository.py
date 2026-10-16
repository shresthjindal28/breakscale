from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.workspace import Workspace


class WorkspaceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        owner_id: UUID,
        name: str,
        graph_data: dict,
        schema_version: int,
    ) -> Workspace:
        workspace = Workspace(
            owner_id=owner_id,
            name=name,
            graph_data=graph_data,
            schema_version=schema_version,
        )

        self.db.add(workspace)
        await self.db.commit()
        await self.db.refresh(workspace)

        return workspace

    async def get_by_id(
        self,
        workspace_id: UUID,
        owner_id: UUID,
    ) -> Workspace | None:
        result = await self.db.execute(
            select(Workspace).where(
                Workspace.id == workspace_id,
                Workspace.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_owner(
        self,
        owner_id: UUID,
    ) -> list[Workspace]:
        result = await self.db.execute(
            select(Workspace)
            .where(Workspace.owner_id == owner_id)
            .order_by(Workspace.updated_at.desc())
        )
        return list(result.scalars().all())

    async def delete(self, workspace: Workspace) -> None:
        await self.db.delete(workspace)
        await self.db.commit()

    async def save(self, workspace: Workspace) -> Workspace:
        await self.db.commit()
        await self.db.refresh(workspace)
        return workspace