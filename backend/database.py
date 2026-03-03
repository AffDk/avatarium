"""Async SQLAlchemy engine, session factory, and DB dependency."""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings

logger = logging.getLogger(__name__)

_is_sqlite = settings.database_url.startswith("sqlite")

# Engine kwargs
_engine_kwargs: dict = {
    "echo": settings.is_development,
    "future": True,
}
if _is_sqlite:
    _engine_kwargs["connect_args"] = {
        "check_same_thread": False,
        "timeout": 30,  # SQLite busy-wait timeout in seconds
    }

engine = create_async_engine(settings.database_url, **_engine_kwargs)


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Set SQLite PRAGMAs for performance and concurrency (WAL mode)."""
    if _is_sqlite:
        async with engine.begin() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA busy_timeout=30000"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
        logger.info("SQLite PRAGMAs applied (WAL, busy_timeout=30s)")


async def create_all() -> None:
    """Create all tables — used for dev/testing only."""
    from backend.models import Base  # noqa: F811

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    """Dispose the engine connection pool."""
    await engine.dispose()
