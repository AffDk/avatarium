"""Pytest fixtures for Avatarium test suite."""

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.models import Base
from backend.database import get_db
from backend.services.auth_service import create_access_token, hash_password
from backend.models.user import User


# ── Test Database (in-memory, shared via StaticPool) ─

TEST_DATABASE_URL = "sqlite+aiosqlite://"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
test_session_factory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Override the DB dependency to use the in-memory test database."""
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── HTTP Client ──────────────────────────────────

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client."""
    from backend.main import create_app

    test_app = create_app()
    test_app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── User Factories ───────────────────────────────

@pytest.fixture
async def test_user() -> User:
    """Create a test user in the database and return it."""
    async with test_session_factory() as session:
        user = User(
            id=uuid.uuid4(),
            email="testuser@example.com",
            display_name="Test User",
            hashed_password=hash_password("TestPassword123"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest.fixture
async def auth_token(test_user: User) -> str:
    """Return a valid JWT token for the test user."""
    return create_access_token(test_user.id)


@pytest.fixture
async def auth_headers(auth_token: str) -> dict[str, str]:
    """Return Authorization headers for the test user."""
    return {"Authorization": f"Bearer {auth_token}"}


# ── DB Session (for direct DB access in tests) ──

@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Direct DB session for test setup/assertions."""
    async with test_session_factory() as session:
        yield session
