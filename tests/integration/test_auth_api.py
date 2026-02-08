"""Integration tests for auth API endpoints.

Tests MUST fail before T012 implementation (Constitution Principle V: Test-First).

Covers:
- POST /api/auth/register (201/409/422)
- POST /api/auth/login (200/401)
- GET /api/auth/me (200/401)
- Unauthenticated access (401)
- Duplicate email registration (409)
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient) -> None:
    """POST /api/auth/register — 201 with valid data."""
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "alice@example.com",
            "password": "StrongPass123",
            "display_name": "Alice",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["display_name"] == "Alice"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    """POST /api/auth/register — 409 when email already exists."""
    payload = {
        "email": "dup@example.com",
        "password": "StrongPass123",
        "display_name": "First",
    }
    resp1 = await client.post("/api/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = await client.post("/api/auth/register", json=payload)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient) -> None:
    """POST /api/auth/register — 422 with invalid email format."""
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "not-an-email",
            "password": "StrongPass123",
            "display_name": "Bob",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient) -> None:
    """POST /api/auth/register — 422 with password < 8 chars."""
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "short@example.com",
            "password": "short",
            "display_name": "Short",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    """POST /api/auth/login — 200 with correct credentials."""
    # Register first
    await client.post(
        "/api/auth/register",
        json={
            "email": "login@example.com",
            "password": "CorrectPass123",
            "display_name": "LoginUser",
        },
    )
    # Login
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "login@example.com",
            "password": "CorrectPass123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "login@example.com"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    """POST /api/auth/login — 401 with wrong password."""
    await client.post(
        "/api/auth/register",
        json={
            "email": "wrong@example.com",
            "password": "CorrectPass123",
            "display_name": "WrongUser",
        },
    )
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "wrong@example.com",
            "password": "WrongPassword",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_email(client: AsyncClient) -> None:
    """POST /api/auth/login — 401 with unknown email."""
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "nobody@example.com",
            "password": "SomePassword123",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient) -> None:
    """GET /api/auth/me — 200 with valid token."""
    # Register to get a token
    reg = await client.post(
        "/api/auth/register",
        json={
            "email": "me@example.com",
            "password": "MyPassword123",
            "display_name": "MeUser",
        },
    )
    token = reg.json()["access_token"]

    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@example.com"
    assert data["display_name"] == "MeUser"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient) -> None:
    """GET /api/auth/me — 401 without token."""
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient) -> None:
    """GET /api/auth/me — 401 with invalid token."""
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid-token-here"},
    )
    assert response.status_code == 401
