"""Page routes — serve Jinja2 HTML templates for browser navigation."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["Pages"])


@router.get("/")
async def landing_page(request: Request):
    """Serve the landing / sign-in page."""
    return templates.TemplateResponse(
        "landing.html", {"request": request, "show_register": False}
    )


@router.get("/login")
async def login_page(request: Request):
    """Serve the landing page scrolled to the login form."""
    return templates.TemplateResponse(
        "landing.html", {"request": request, "show_register": False}
    )


@router.get("/register")
async def register_page(request: Request):
    """Serve the landing page with the register form visible."""
    return templates.TemplateResponse(
        "landing.html", {"request": request, "show_register": True}
    )


@router.get("/logout")
async def logout_page(request: Request):
    """Clear auth state and redirect to landing page."""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    return response


@router.get("/dashboard")
async def dashboard_page(request: Request):
    """Serve the user dashboard."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/new-project")
async def new_project_page(request: Request):
    """Serve the new project creation form."""
    return templates.TemplateResponse("new_project.html", {"request": request})


@router.get("/projects/{project_id}")
async def project_detail_page(request: Request, project_id: str):
    """Serve the project detail / generation progress page."""
    return templates.TemplateResponse(
        "project_detail.html", {"request": request, "project_id": project_id}
    )
