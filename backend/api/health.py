"""Health check endpoint for deployment readiness."""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/api/health")
async def health_check() -> dict[str, str]:
    """Return OK status for load balancers and monitoring."""
    return {"status": "ok"}
