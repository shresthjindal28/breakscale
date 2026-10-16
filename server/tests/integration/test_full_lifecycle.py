"""Opt-in live test: requires a migrated disposable database/Redis and a running RQ worker.

Run with BREAKSCALE_INTEGRATION=1 uv run pytest tests/integration/test_full_lifecycle.py -v -s
Uses generated accounts and removes only its own data.
"""

import asyncio
import os
import secrets

import httpx
import pytest
from sqlalchemy import delete

from app.db.models.user import User
from app.db.session import AsyncSessionLocal, engine
from app.main import app


@pytest.mark.skipif(
    os.getenv("BREAKSCALE_INTEGRATION") != "1", reason="requires live PostgreSQL, Redis and RQ worker"
)
@pytest.mark.asyncio
async def test_complete_application():
    users = []
    origin = {"Origin": "http://localhost:3000"}
    transport = httpx.ASGITransport(app=app)
    workspace_id = None
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=origin) as client:
        try:
            for index in range(2):
                email = f"integration-{secrets.token_hex(6)}@example.com"
                password = secrets.token_urlsafe(20)
                response = await client.post(
                    "/api/v1/auth/register",
                    json={"name": "Integration test", "email": email, "password": password},
                )
                assert response.status_code == 201, response.text
                data = response.json()
                users.append(data["id"])
                assert "password_hash" not in data
                response = await client.post(
                    "/api/v1/auth/login", json={"email": email, "password": password}
                )
                assert response.status_code == 200, response.text
                token = response.json()["access_token"]
                if index == 0:
                    first = token
                    cookie = client.cookies.get("breakscale_refresh")
                    response = await client.post("/api/v1/auth/refresh")
                    assert response.status_code == 200, response.text
                    newcookie = client.cookies.get("breakscale_refresh")
                    assert cookie != newcookie
                    async with httpx.AsyncClient(
                        transport=transport, base_url="http://test", headers=origin
                    ) as attacker:
                        attacker.cookies.set("breakscale_refresh", cookie, path="/api/v1/auth")
                        assert (await attacker.post("/api/v1/auth/refresh")).status_code == 401
                    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
                    print(
                        "Registration/login + refresh rotation and token-family replay revocation verified",
                        flush=True,
                    )
                else:
                    second = token
            client.headers["Authorization"] = "Bearer " + first
            response = await client.get("/api/v1/users/me")
            assert response.status_code == 200, response.text
            assert response.json()["id"] == users[0]
            graph = {
                "nodes": [
                    {"id": "client", "type": "client", "data": {"rps": 20}},
                    {"id": "api", "type": "service", "data": {"capacity_rps": 100}},
                    {"id": "cache", "type": "cache"},
                    {"id": "db", "type": "database"},
                ],
                "edges": [
                    {"id": str(i), "source": a, "target": b}
                    for i, (a, b) in enumerate([("client", "api"), ("api", "cache"), ("cache", "db")])
                ],
            }
            response = await client.post(
                "/api/v1/workspaces", json={"name": "Auth worker verification", "graph_data": graph}
            )
            assert response.status_code == 201, response.text
            workspace_id = response.json()["id"]
            client.headers["Authorization"] = "Bearer " + second
            assert (await client.get("/api/v1/workspaces/" + workspace_id)).status_code == 404
            assert (
                await client.post("/api/v1/simulations", json={"workspace_id": workspace_id})
            ).status_code == 404
            client.headers["Authorization"] = "Bearer " + first
            response = await client.post(
                "/api/v1/simulations", json={"workspace_id": workspace_id, "duration_seconds": 2}
            )
            assert response.status_code == 202, response.text
            run = response.json()
            run_id = run["id"]
            print("Simulation enqueued:", run["status"], flush=True)
            states = [run["status"]]
            for _ in range(100):
                await asyncio.sleep(0.5)
                response = await client.get("/api/v1/simulations/" + run_id)
                assert response.status_code == 200, response.text
                status = response.json()["status"]
                states.append(status)
                if status in ("completed", "failed", "cancelled"):
                    break
            assert status == "completed", states
            response = await client.get(f"/api/v1/simulations/{run_id}/results")
            assert response.status_code == 200, response.text
            assert response.json()["summary"]["completed"] > 0
            response = await client.get(f"/api/v1/simulations/{run_id}/trace")
            assert response.status_code == 200, response.text
            assert response.json()["events"] and response.json()["events"][-1]["timestamp"] <= 2
            print(
                "RQ lifecycle + persisted metrics and trace verified; observed states:",
                sorted(set(states)),
                flush=True,
            )
            client.headers["Authorization"] = "Bearer " + second
            for path in (
                f"/api/v1/simulations/{run_id}",
                f"/api/v1/simulations/{run_id}/results",
                f"/api/v1/simulations/{run_id}/trace",
            ):
                assert (await client.get(path)).status_code == 404
            assert (await client.delete(f"/api/v1/simulations/{run_id}")).status_code == 404
            print("Cross-user workspace/run/result/trace/delete isolation verified", flush=True)
            client.headers["Authorization"] = "Bearer " + first
            response = await client.post(
                "/api/v1/simulations", json={"workspace_id": workspace_id, "duration_seconds": 300}
            )
            assert response.status_code == 202, response.text
            cancel_id = response.json()["id"]
            for _ in range(60):
                status_response = await client.get(f"/api/v1/simulations/{cancel_id}")
                if status_response.json()["status"] == "running":
                    break
                await asyncio.sleep(0.25)
            assert status_response.json()["status"] == "running", status_response.text
            print("Cancellation target confirmed running", flush=True)
            response = await client.post(f"/api/v1/simulations/{cancel_id}/cancel")
            assert response.status_code == 200, response.text
            for _ in range(100):
                response = await client.get(f"/api/v1/simulations/{cancel_id}")
                if response.json()["status"] == "cancelled":
                    break
                await asyncio.sleep(0.5)
            assert response.json()["status"] == "cancelled", response.text
            print("Cooperative/pending cancellation verified", flush=True)
            client.headers["Authorization"] = "Bearer " + second
            assert (await client.post("/api/v1/auth/logout")).status_code == 204
            assert (await client.post("/api/v1/auth/refresh")).status_code == 401
            print("Logout revocation verified", flush=True)
        finally:
            async with AsyncSessionLocal() as db:
                from uuid import UUID

                await db.execute(delete(User).where(User.id.in_([UUID(value) for value in users])))
                await db.commit()
            await engine.dispose()
            print("Disposable accounts, workspaces and runs removed", flush=True)
