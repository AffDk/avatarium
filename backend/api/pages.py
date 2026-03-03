"""Page routes — serve Jinja2 HTML templates for browser navigation."""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.project import Project, ProjectStatus
from backend.models.video import FinalVideo, VideoClip
from backend.services.auth_service import decode_access_token, get_user_by_id

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["Pages"])


async def _get_current_user_or_none(request: Request, db: AsyncSession):
    """Read the access_token cookie an return the User, or None if invalid/missing."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    user_id = decode_access_token(token)
    if user_id is None:
        return None
    return await get_user_by_id(db, user_id)


def _ctx(request: Request, user=None, **extra):
    """Build a template context dict with request + user + extras."""
    return {"request": request, "user": user, **extra}


@router.get("/")
async def landing_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Serve the landing / sign-in page. Redirect to dashboard if already logged in."""
    user = await _get_current_user_or_none(request, db)
    if user is not None:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("landing.html", _ctx(request, show_register=False))


@router.get("/login")
async def login_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Serve the landing page scrolled to the login form."""
    user = await _get_current_user_or_none(request, db)
    if user is not None:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("landing.html", _ctx(request, show_register=False))


@router.get("/register")
async def register_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Serve the landing page with the register form visible."""
    user = await _get_current_user_or_none(request, db)
    if user is not None:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("landing.html", _ctx(request, show_register=True))


@router.get("/logout")
async def logout_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Clear auth state, abort any active generations, and redirect to landing page."""
    # Reset any generating/concatenating projects before clearing auth
    token = request.cookies.get("access_token")
    if token:
        user_id = decode_access_token(token)
        if user_id:
            user = await get_user_by_id(db, user_id)
            if user:
                result = await db.execute(
                    select(Project).where(
                        Project.user_id == user.id,
                        Project.status.in_([
                            ProjectStatus.GENERATING,
                            ProjectStatus.CONCATENATING,
                        ]),
                    )
                )
                for project in result.scalars().all():
                    project.status = ProjectStatus.REVIEWING
                    # Delete incomplete clips
                    clips_result = await db.execute(
                        select(VideoClip).where(VideoClip.project_id == project.id)
                    )
                    for clip in clips_result.scalars().all():
                        await db.delete(clip)
                    # Delete any partial final video
                    fv_result = await db.execute(
                        select(FinalVideo).where(FinalVideo.project_id == project.id)
                    )
                    for fv in fv_result.scalars().all():
                        await db.delete(fv)
                await db.commit()

    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    return response


@router.get("/dashboard")
async def dashboard_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Serve the user dashboard. Redirect to login if not authenticated."""
    user = await _get_current_user_or_none(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("dashboard.html", _ctx(request, user))


@router.get("/new-project")
async def new_project_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Serve the new project creation form."""
    user = await _get_current_user_or_none(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("new_project.html", _ctx(request, user))
    return templates.TemplateResponse("new_project.html", {"request": request})


@router.get("/projects/{project_id}")
async def project_detail_page(request: Request, project_id: str, db: AsyncSession = Depends(get_db)):
    """Serve the project detail / generation progress page."""
    user = await _get_current_user_or_none(request, db)
    if user is None:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(
        "project_detail.html", _ctx(request, user, project_id=project_id)
    )
