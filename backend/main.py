"""FastAPI application factory — entrypoint."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from backend.config import settings
from backend.database import create_all, dispose_engine
from backend.logging_config import setup_logging
from backend.middleware.rate_limit import limiter

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: create tables (dev), configure logging. Shutdown: dispose engine."""
    setup_logging()
    if settings.is_development:
        await create_all()
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="Avatarium",
        description="AI avatar video generation platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── Rate limiter ────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── Session middleware (required for OAuth state) ──
    app.add_middleware(SessionMiddleware, secret_key=settings.app_secret_key)

    # ── Static files ────────────────────────────
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # ── Routers ─────────────────────────────────
    from backend.api.health import router as health_router
    from backend.api.auth import router as auth_router
    from backend.api.projects import router as projects_router
    from backend.api.scenarios import router as scenarios_router
    from backend.api.generation import router as generation_router
    from backend.api.pages import router as pages_router

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(projects_router)
    app.include_router(scenarios_router)
    app.include_router(generation_router)
    app.include_router(pages_router)

    return app


# Jinja2 templates — importable by route handlers
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Application instance for uvicorn
app = create_app()
