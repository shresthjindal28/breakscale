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


@pytest.fixture(autouse=True)
def fake_queue(monkeypatch):
    from unittest.mock import Mock
    redis = AsyncMock()
    redis.eval.return_value = 1
    monkeypatch.setattr("app.services.simulation_service.Redis.from_url", Mock(return_value=redis))
    monkeypatch.setattr("app.services.simulation_service.enqueue_simulation", Mock())


@pytest.mark.asyncio
async def test_success_persists_snapshot_and_pending_status():
    service, workspace = setup_service()
    simulation = await service.create(uuid4(), SimulationCreate(workspace_id=workspace.id, duration_seconds=1))
    assert simulation.status == "pending"
    assert simulation.graph_snapshot == workspace.graph_data
    assert simulation.graph_snapshot is not workspace.graph_data
    service.repo.save_result.assert_not_called()
    service.db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_enqueue_failure_persists_status_and_error(monkeypatch):
    from unittest.mock import Mock
    monkeypatch.setattr("app.services.simulation_service.enqueue_simulation", Mock(side_effect=RuntimeError("queue down")))
    service, workspace = setup_service()
    with pytest.raises(HTTPException) as error:
        await service.create(uuid4(), SimulationCreate(workspace_id=workspace.id))
    assert error.value.status_code == 503
    simulation = service.repo.create.call_args.args[0]
    assert simulation.status == "failed"
    result = service.repo.save_result.call_args.args[0]
    assert result.summary["error_type"] == "EnqueueError"


@pytest.mark.asyncio
async def test_invalid_graph_is_rejected_before_enqueue():
    service, workspace = setup_service()
    workspace.graph_data = {"nodes": [], "edges": []}
    with pytest.raises(HTTPException) as error:
        await service.create(uuid4(), SimulationCreate(workspace_id=workspace.id))
    assert error.value.status_code == 422
    service.repo.create.assert_not_called()


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


def test_unauthenticated_resources_rejected():
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as client:
        assert client.get("/api/v1/workspaces").status_code == 401
        assert client.get("/api/v1/users/me").status_code == 401


@pytest.mark.asyncio
async def test_delete_checks_ownership_before_mutation():
    service, workspace = setup_service()
    simulation = SimpleNamespace(workspace_id=workspace.id, status="completed")
    service.repo.get.return_value = simulation
    await service.delete(uuid4(), uuid4())
    service.db.delete.assert_awaited_once_with(simulation)
    service.db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_rejects_active_simulation():
    service, workspace = setup_service()
    service.repo.get.return_value = SimpleNamespace(workspace_id=workspace.id, status="running")
    with pytest.raises(HTTPException) as error:
        await service.delete(uuid4(), uuid4())
    assert error.value.status_code == 409
    service.db.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_foreign_run_is_denied():
    service, workspace = setup_service()
    service.repo.get.return_value = SimpleNamespace(workspace_id=workspace.id, status="completed")
    service.workspaces.get.side_effect = HTTPException(404, "Workspace not found")
    with pytest.raises(HTTPException):
        await service.delete(uuid4(), uuid4())
    service.db.delete.assert_not_called()
