from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas.simulation import SimulationCreate
from app.services.simulation_service import SimulationService


def setup_service():
    service = SimulationService(AsyncMock())
    workspace = SimpleNamespace(id=uuid4(), graph_data={
        "nodes": [{"id": "client", "type": "client", "data": {"rps": 10}},
                  {"id": "api", "type": "service"}],
        "edges": [{"id": "e", "source": "client", "target": "api"}],
    })
    service.workspaces = SimpleNamespace(get=AsyncMock(return_value=workspace))

    async def create(simulation):
        simulation.id = uuid4()
        return simulation

    service.repo = SimpleNamespace(
        create=AsyncMock(side_effect=create), save_result=AsyncMock(),
        get=AsyncMock(return_value=None), get_result=AsyncMock(return_value=None),
        list_by_workspace=AsyncMock(return_value=[]),
    )
    return service, workspace


@pytest.mark.asyncio
async def test_success_persists_snapshot_and_summary():
    service, workspace = setup_service()
    simulation = await service.create(uuid4(), SimulationCreate(workspace_id=workspace.id, duration_seconds=1))
    assert simulation.status == "completed"
    assert simulation.graph_snapshot == workspace.graph_data
    assert simulation.graph_snapshot is not workspace.graph_data
    result = service.repo.save_result.call_args.args[0]
    assert result.summary["completed"] > 0
    assert result.summary["latency"]["p95_ms"] > 0
    assert "latencies_ms" not in result.summary
    assert "api" in result.node_metrics
    assert service.db.commit.await_count == 2


@pytest.mark.asyncio
async def test_failed_run_persists_status_and_error():
    service, workspace = setup_service()
    workspace.graph_data = {"nodes": [], "edges": []}
    with pytest.raises(HTTPException) as error:
        await service.create(uuid4(), SimulationCreate(workspace_id=workspace.id))
    assert error.value.status_code == 422
    simulation = service.repo.create.call_args.args[0]
    assert simulation.status == "failed"
    result = service.repo.save_result.call_args.args[0]
    assert "Invalid architecture" in result.summary["error"]
    assert service.db.commit.await_count == 2


@pytest.mark.asyncio
async def test_foreign_workspace_cannot_start_simulation():
    service, workspace = setup_service()
    service.workspaces.get.side_effect = HTTPException(404, "Workspace not found")
    with pytest.raises(HTTPException):
        await service.create(uuid4(), SimulationCreate(workspace_id=workspace.id))
    service.repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_missing_simulation():
    service, _ = setup_service()
    with pytest.raises(HTTPException) as error:
        await service.get(uuid4(), uuid4())
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_result_and_list_require_workspace_ownership():
    service, workspace = setup_service()
    service.repo.get.return_value = SimpleNamespace(workspace_id=workspace.id)
    service.workspaces.get.side_effect = HTTPException(404, "Workspace not found")
    with pytest.raises(HTTPException):
        await service.get_result(uuid4(), uuid4())
    service.repo.get_result.assert_not_called()
    with pytest.raises(HTTPException):
        await service.list(workspace.id, uuid4())
    service.repo.list_by_workspace.assert_not_called()


def test_development_auth_disabled(monkeypatch):
    from app.api.v1.simulations import get_dev_owner_id
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "DEBUG", False)
    with pytest.raises(HTTPException) as error:
        get_dev_owner_id()
    assert error.value.status_code == 403
