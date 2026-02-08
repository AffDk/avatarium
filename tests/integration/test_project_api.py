"""Integration tests for project and photo API endpoints.

Tests MUST fail before T025 implementation (Constitution Principle V: Test-First).

Covers:
- POST /api/projects (201/422)
- GET /api/projects (200, user-scoped pagination)
- GET /api/projects/{id} (200/404)
- DELETE /api/projects/{id} (204/404)
- POST /api/projects/{id}/photos (201 with person grouping / 400 invalid name)
- GET /api/projects/{id}/photos (200 grouped by person)
- DELETE /api/projects/{id}/photos/{photoId} (204/404)
- Unauthenticated access (401)
"""

import io
import uuid

import pytest
from httpx import AsyncClient


# ── Helper ────────────────────────────────────────────────


async def _register_and_get_headers(client: AsyncClient, email: str = "proj@example.com") -> dict:
    """Register a user and return auth headers."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "StrongPass123", "display_name": "ProjUser"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_project(
    client: AsyncClient,
    headers: dict,
    title: str = "Test Project",
    video_style: str = "animation",
) -> dict:
    """Create a project and return its response data."""
    resp = await client.post(
        "/api/projects",
        json={"title": title, "video_style": video_style},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


# ── Project CRUD ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_project_success(client: AsyncClient) -> None:
    """POST /api/projects — 201 with valid data."""
    headers = await _register_and_get_headers(client)
    resp = await client.post(
        "/api/projects",
        json={"title": "My Avatar Video", "video_style": "animation"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "My Avatar Video"
    assert data["video_style"] == "animation"
    assert data["status"] == "draft"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_project_movie_like(client: AsyncClient) -> None:
    """POST /api/projects — 201 with movie_like style."""
    headers = await _register_and_get_headers(client)
    resp = await client.post(
        "/api/projects",
        json={"title": "Movie Project", "video_style": "movie_like"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["video_style"] == "movie_like"


@pytest.mark.asyncio
async def test_create_project_invalid_style(client: AsyncClient) -> None:
    """POST /api/projects — 422 with invalid video_style."""
    headers = await _register_and_get_headers(client)
    resp = await client.post(
        "/api/projects",
        json={"title": "Bad Style", "video_style": "invalid_style"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_project_missing_title(client: AsyncClient) -> None:
    """POST /api/projects — 422 with missing title."""
    headers = await _register_and_get_headers(client)
    resp = await client.post(
        "/api/projects",
        json={"video_style": "animation"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_project_unauthenticated(client: AsyncClient) -> None:
    """POST /api/projects — 401 without auth."""
    resp = await client.post(
        "/api/projects",
        json={"title": "No Auth", "video_style": "animation"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient) -> None:
    """GET /api/projects — 200 with paginated list, user-scoped."""
    headers = await _register_and_get_headers(client)
    await _create_project(client, headers, title="Project A")
    await _create_project(client, headers, title="Project B")

    resp = await client.get("/api/projects", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) == 2
    assert data["total"] == 2
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_list_projects_user_scoped(client: AsyncClient) -> None:
    """GET /api/projects — only shows current user's projects."""
    headers_a = await _register_and_get_headers(client, email="usera@example.com")
    headers_b = await _register_and_get_headers(client, email="userb@example.com")

    await _create_project(client, headers_a, title="User A Project")
    await _create_project(client, headers_b, title="User B Project")

    resp_a = await client.get("/api/projects", headers=headers_a)
    assert resp_a.status_code == 200
    assert len(resp_a.json()["items"]) == 1
    assert resp_a.json()["items"][0]["title"] == "User A Project"


@pytest.mark.asyncio
async def test_list_projects_unauthenticated(client: AsyncClient) -> None:
    """GET /api/projects — 401 without auth."""
    resp = await client.get("/api/projects")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_project_detail(client: AsyncClient) -> None:
    """GET /api/projects/{id} — 200 with project details."""
    headers = await _register_and_get_headers(client)
    project = await _create_project(client, headers)

    resp = await client.get(f"/api/projects/{project['id']}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == project["id"]
    assert data["title"] == "Test Project"
    assert "persons" in data


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient) -> None:
    """GET /api/projects/{id} — 404 for non-existent project."""
    headers = await _register_and_get_headers(client)
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/projects/{fake_id}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_project_other_user(client: AsyncClient) -> None:
    """GET /api/projects/{id} — 404 when accessing another user's project."""
    headers_a = await _register_and_get_headers(client, email="owner@example.com")
    headers_b = await _register_and_get_headers(client, email="stranger@example.com")

    project = await _create_project(client, headers_a)
    resp = await client.get(f"/api/projects/{project['id']}", headers=headers_b)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient) -> None:
    """DELETE /api/projects/{id} — 204 successfully deletes project."""
    headers = await _register_and_get_headers(client)
    project = await _create_project(client, headers)

    resp = await client.delete(f"/api/projects/{project['id']}", headers=headers)
    assert resp.status_code == 204

    # Verify it's gone
    resp = await client.get(f"/api/projects/{project['id']}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_not_found(client: AsyncClient) -> None:
    """DELETE /api/projects/{id} — 404 for non-existent project."""
    headers = await _register_and_get_headers(client)
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/api/projects/{fake_id}", headers=headers)
    assert resp.status_code == 404


# ── Photo Upload ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_photos_valid(client: AsyncClient) -> None:
    """POST /api/projects/{id}/photos — 201 with valid named photos."""
    headers = await _register_and_get_headers(client)
    project = await _create_project(client, headers)

    # Simulate multipart file upload
    files = [
        ("photos", ("alice_1.jpg", io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 100), "image/jpeg")),
        ("photos", ("alice_2.png", io.BytesIO(b"\x89PNG" + b"\x00" * 100), "image/png")),
        ("photos", ("bob_1.jpg", io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 100), "image/jpeg")),
    ]
    resp = await client.post(
        f"/api/projects/{project['id']}/photos",
        files=files,
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["uploaded"] == 3
    assert "alice" in data["persons_created"]
    assert "bob" in data["persons_created"]


@pytest.mark.asyncio
async def test_upload_photos_invalid_filename(client: AsyncClient) -> None:
    """POST /api/projects/{id}/photos — 400 with invalid filename format."""
    headers = await _register_and_get_headers(client)
    project = await _create_project(client, headers)

    files = [
        ("photos", ("myphoto.jpg", io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 100), "image/jpeg")),
    ]
    resp = await client.post(
        f"/api/projects/{project['id']}/photos",
        files=files,
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_photos_invalid_mime(client: AsyncClient) -> None:
    """POST /api/projects/{id}/photos — 400 with unsupported file type."""
    headers = await _register_and_get_headers(client)
    project = await _create_project(client, headers)

    files = [
        ("photos", ("person1_1.gif", io.BytesIO(b"GIF89a" + b"\x00" * 100), "image/gif")),
    ]
    resp = await client.post(
        f"/api/projects/{project['id']}/photos",
        files=files,
        headers=headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_photos_unauthenticated(client: AsyncClient) -> None:
    """POST /api/projects/{id}/photos — 401 without auth."""
    fake_id = str(uuid.uuid4())
    files = [
        ("photos", ("alice_1.jpg", io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 100), "image/jpeg")),
    ]
    resp = await client.post(f"/api/projects/{fake_id}/photos", files=files)
    assert resp.status_code == 401


# ── Photo Listing ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_photos_grouped(client: AsyncClient) -> None:
    """GET /api/projects/{id}/photos — 200 with photos grouped by person."""
    headers = await _register_and_get_headers(client)
    project = await _create_project(client, headers)

    # Upload photos for two persons
    files = [
        ("photos", ("alice_1.jpg", io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 100), "image/jpeg")),
        ("photos", ("bob_1.jpg", io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 100), "image/jpeg")),
    ]
    await client.post(f"/api/projects/{project['id']}/photos", files=files, headers=headers)

    resp = await client.get(f"/api/projects/{project['id']}/photos", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "persons" in data
    person_names = [p["person"]["name"] for p in data["persons"]]
    assert "alice" in person_names
    assert "bob" in person_names


# ── Photo Delete ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_photo(client: AsyncClient) -> None:
    """DELETE /api/projects/{id}/photos/{photoId} — 204."""
    headers = await _register_and_get_headers(client)
    project = await _create_project(client, headers)

    files = [
        ("photos", ("alice_1.jpg", io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 100), "image/jpeg")),
    ]
    upload_resp = await client.post(
        f"/api/projects/{project['id']}/photos",
        files=files,
        headers=headers,
    )
    photo_id = upload_resp.json()["photos"][0]["id"]

    resp = await client.delete(
        f"/api/projects/{project['id']}/photos/{photo_id}",
        headers=headers,
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_photo_not_found(client: AsyncClient) -> None:
    """DELETE /api/projects/{id}/photos/{photoId} — 404 for non-existent photo."""
    headers = await _register_and_get_headers(client)
    project = await _create_project(client, headers)
    fake_photo_id = str(uuid.uuid4())

    resp = await client.delete(
        f"/api/projects/{project['id']}/photos/{fake_photo_id}",
        headers=headers,
    )
    assert resp.status_code == 404


# ── Delete Project Cascades ──────────────────────────────


@pytest.mark.asyncio
async def test_delete_project_cascades_photos(client: AsyncClient) -> None:
    """DELETE /api/projects/{id} — 204, photos also deleted."""
    headers = await _register_and_get_headers(client)
    project = await _create_project(client, headers)

    files = [
        ("photos", ("alice_1.jpg", io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 100), "image/jpeg")),
    ]
    await client.post(f"/api/projects/{project['id']}/photos", files=files, headers=headers)

    resp = await client.delete(f"/api/projects/{project['id']}", headers=headers)
    assert resp.status_code == 204

    # Verify project and photos are gone
    resp = await client.get(f"/api/projects/{project['id']}/photos", headers=headers)
    assert resp.status_code == 404
