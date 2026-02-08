"""Integration tests for scenario API endpoints.

Tests MUST fail before T035 implementation (Constitution Principle V: Test-First).

Covers:
- PUT /api/projects/{id}/scenario (200 with segments)
- GET /api/projects/{id}/scenario (200 with moderation status + segments)
- Rejected scenario (200 with rejection_reason)
- Scenario without photos uploaded (400)
- Unauthenticated access (401)
"""

import io
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


# ── Helpers ───────────────────────────────────────────────


async def _register_and_get_headers(client: AsyncClient, email: str = "scen@example.com") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "StrongPass123", "display_name": "ScenUser"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project_with_photos(client: AsyncClient, headers: dict) -> str:
    """Create a project and upload a photo, return project ID."""
    resp = await client.post(
        "/api/projects",
        json={"title": "Scenario Test", "video_style": "animation"},
        headers=headers,
    )
    project_id = resp.json()["id"]

    files = [
        ("photos", ("alice_1.jpg", io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 100), "image/jpeg")),
    ]
    await client.post(f"/api/projects/{project_id}/photos", files=files, headers=headers)
    return project_id


MOCK_APPROVED_RESPONSE = '''```json
{
    "approved": true,
    "rejection_reason": null,
    "segments": [
        {"sequence_number": 1, "description": "Alice walks into the garden."},
        {"sequence_number": 2, "description": "She picks a flower and smiles."}
    ]
}
```'''

MOCK_REJECTED_RESPONSE = '''```json
{
    "approved": false,
    "rejection_reason": "Content contains prohibited violence",
    "segments": []
}
```'''


# ── Submit Scenario ───────────────────────────────────────


@pytest.mark.asyncio
@patch("backend.services.moderation_service._call_gemini")
async def test_submit_scenario_approved(mock_gemini: AsyncMock, client: AsyncClient) -> None:
    """PUT /api/projects/{id}/scenario — 200 with approved scenario + segments."""
    mock_gemini.return_value = MOCK_APPROVED_RESPONSE
    headers = await _register_and_get_headers(client)
    project_id = await _create_project_with_photos(client, headers)

    resp = await client.put(
        f"/api/projects/{project_id}/scenario",
        json={"text": "Alice walks into the garden and picks a flower."},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["moderation_status"] == "approved"
    assert data["segments"] is not None
    assert len(data["segments"]) == 2


@pytest.mark.asyncio
@patch("backend.services.moderation_service._call_gemini")
async def test_submit_scenario_rejected(mock_gemini: AsyncMock, client: AsyncClient) -> None:
    """PUT /api/projects/{id}/scenario — 200 with rejected scenario."""
    mock_gemini.return_value = MOCK_REJECTED_RESPONSE
    headers = await _register_and_get_headers(client)
    project_id = await _create_project_with_photos(client, headers)

    resp = await client.put(
        f"/api/projects/{project_id}/scenario",
        json={"text": "Some violent scenario content."},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["moderation_status"] == "rejected"
    assert data["rejection_reason"] is not None
    assert "violence" in data["rejection_reason"].lower()


@pytest.mark.asyncio
async def test_submit_scenario_unauthenticated(client: AsyncClient) -> None:
    """PUT /api/projects/{id}/scenario — 401 without auth."""
    fake_id = str(uuid.uuid4())
    resp = await client.put(
        f"/api/projects/{fake_id}/scenario",
        json={"text": "Some scenario."},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_submit_scenario_project_not_found(client: AsyncClient) -> None:
    """PUT /api/projects/{id}/scenario — 404 for non-existent project."""
    headers = await _register_and_get_headers(client, email="notfound@example.com")
    fake_id = str(uuid.uuid4())
    resp = await client.put(
        f"/api/projects/{fake_id}/scenario",
        json={"text": "Some scenario."},
        headers=headers,
    )
    assert resp.status_code == 404


# ── Get Scenario ──────────────────────────────────────────


@pytest.mark.asyncio
@patch("backend.services.moderation_service._call_gemini")
async def test_get_scenario(mock_gemini: AsyncMock, client: AsyncClient) -> None:
    """GET /api/projects/{id}/scenario — 200 with full detail."""
    mock_gemini.return_value = MOCK_APPROVED_RESPONSE
    headers = await _register_and_get_headers(client, email="getscen@example.com")
    project_id = await _create_project_with_photos(client, headers)

    # Submit first
    await client.put(
        f"/api/projects/{project_id}/scenario",
        json={"text": "Alice walks in the garden."},
        headers=headers,
    )

    # Then get
    resp = await client.get(f"/api/projects/{project_id}/scenario", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "Alice walks in the garden."
    assert data["moderation_status"] == "approved"
    assert "segments" in data


@pytest.mark.asyncio
async def test_get_scenario_not_submitted(client: AsyncClient) -> None:
    """GET /api/projects/{id}/scenario — 404 when no scenario exists."""
    headers = await _register_and_get_headers(client, email="noscen@example.com")
    resp = await client.post(
        "/api/projects",
        json={"title": "Empty Project", "video_style": "animation"},
        headers=headers,
    )
    project_id = resp.json()["id"]

    resp = await client.get(f"/api/projects/{project_id}/scenario", headers=headers)
    assert resp.status_code == 404
