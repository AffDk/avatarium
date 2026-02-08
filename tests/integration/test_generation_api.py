"""Integration tests for generation API endpoints.

Tests MUST fail before T045 implementation (Constitution Principle V: Test-First).

Covers:
- POST /api/projects/{id}/generate (202 accepted)
- 400 when no approved scenario
- 409 when pipeline already running
- GET /api/projects/{id}/status (200 with per-segment progress)
- Unauthenticated access (401)
"""

import io
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


# ── Helpers ───────────────────────────────────────────────


async def _register_and_get_headers(client: AsyncClient, email: str = "gen@example.com") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "StrongPass123", "display_name": "GenUser"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


MOCK_APPROVED_RESPONSE = '''{"approved": true, "rejection_reason": null, "segments": [{"sequence_number": 1, "description": "Scene one."}, {"sequence_number": 2, "description": "Scene two."}]}'''


async def _create_ready_project(client: AsyncClient, headers: dict) -> str:
    """Create a project with photos and approved scenario."""
    resp = await client.post(
        "/api/projects",
        json={"title": "Gen Test", "video_style": "animation"},
        headers=headers,
    )
    project_id = resp.json()["id"]

    # Upload photo
    files = [
        ("photos", ("alice_1.jpg", io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 100), "image/jpeg")),
    ]
    await client.post(f"/api/projects/{project_id}/photos", files=files, headers=headers)

    # Submit scenario (mocked Gemini)
    with patch("backend.services.moderation_service._call_gemini", new_callable=AsyncMock) as mock:
        mock.return_value = MOCK_APPROVED_RESPONSE
        await client.put(
            f"/api/projects/{project_id}/scenario",
            json={"text": "Alice walks in the park."},
            headers=headers,
        )

    return project_id


# ── Generate Endpoint ─────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_accepted(client: AsyncClient) -> None:
    """POST /api/projects/{id}/generate — 202 when project is ready."""
    headers = await _register_and_get_headers(client)
    project_id = await _create_ready_project(client, headers)

    with patch("backend.api.generation.launch_pipeline", new_callable=AsyncMock):
        resp = await client.post(
            f"/api/projects/{project_id}/generate",
            headers=headers,
        )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] in ("generating", "submitted")


@pytest.mark.asyncio
async def test_generate_no_scenario(client: AsyncClient) -> None:
    """POST /api/projects/{id}/generate — 400 when no approved scenario."""
    headers = await _register_and_get_headers(client, email="noscen2@example.com")
    resp = await client.post(
        "/api/projects",
        json={"title": "No Scenario", "video_style": "animation"},
        headers=headers,
    )
    project_id = resp.json()["id"]

    resp = await client.post(
        f"/api/projects/{project_id}/generate",
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_generate_unauthenticated(client: AsyncClient) -> None:
    """POST /api/projects/{id}/generate — 401 without auth."""
    fake_id = str(uuid.uuid4())
    resp = await client.post(f"/api/projects/{fake_id}/generate")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_generate_conflict_already_running(client: AsyncClient) -> None:
    """POST /api/projects/{id}/generate — 409 when pipeline already running."""
    headers = await _register_and_get_headers(client, email="conflict@example.com")
    project_id = await _create_ready_project(client, headers)

    # First generate call — should succeed (202)
    with patch("backend.api.generation.launch_pipeline", new_callable=AsyncMock):
        resp1 = await client.post(
            f"/api/projects/{project_id}/generate",
            headers=headers,
        )
    assert resp1.status_code == 202

    # Second generate call — should conflict (409) since pipeline is already running
    with patch("backend.api.generation.launch_pipeline", new_callable=AsyncMock):
        resp2 = await client.post(
            f"/api/projects/{project_id}/generate",
            headers=headers,
        )
    assert resp2.status_code == 409


# ── Status Endpoint ───────────────────────────────────────


@pytest.mark.asyncio
async def test_get_status(client: AsyncClient) -> None:
    """GET /api/projects/{id}/status — 200 with pipeline status."""
    headers = await _register_and_get_headers(client, email="status@example.com")
    project_id = await _create_ready_project(client, headers)

    resp = await client.get(
        f"/api/projects/{project_id}/status",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "project_id" in data


@pytest.mark.asyncio
async def test_get_status_unauthenticated(client: AsyncClient) -> None:
    """GET /api/projects/{id}/status — 401 without auth."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/projects/{fake_id}/status")
    assert resp.status_code == 401
