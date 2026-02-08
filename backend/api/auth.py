"""Auth API routes — register, login, Google OAuth, me."""

import secrets

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.config import Config

from backend.config import settings
from backend.database import get_db
from backend.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from backend.services.auth_service import (
    authenticate_user,
    create_access_token,
    decode_access_token,
    get_or_create_google_user,
    get_user_by_id,
    register_user,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])

security = HTTPBearer(auto_error=False)

# ── Google OAuth via Authlib ────────────────────
_oauth_config = Config(environ={
    "GOOGLE_CLIENT_ID": settings.google_client_id,
    "GOOGLE_CLIENT_SECRET": settings.google_client_secret,
})
oauth = OAuth(config=_oauth_config)
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

security = HTTPBearer(auto_error=False)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> UserResponse:
    """Dependency: extract and validate JWT from Authorization header."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserResponse.model_validate(user)


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=AuthResponse)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Register a new user with email/password."""
    try:
        user = await register_user(
            db,
            email=body.email,
            password=body.password,
            display_name=body.display_name,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    token = create_access_token(user.id)
    return AuthResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticate with email/password and get JWT."""
    user = await authenticate_user(db, email=body.email, password=body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(user.id)
    return AuthResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Return the currently authenticated user."""
    return current_user


# ── Google OAuth endpoints ──────────────────────


@router.get("/google")
async def google_oauth_redirect(request: Request):
    """Redirect to Google OAuth consent screen."""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    return await oauth.google.authorize_redirect(
        request,
        settings.google_redirect_uri,
        state=state,
    )


@router.get("/google/callback")
async def google_oauth_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth callback — exchange code for token, create/find user, redirect to dashboard."""
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google authentication failed",
        )

    userinfo = token.get("userinfo")
    if userinfo is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not retrieve user info from Google",
        )

    google_id = userinfo["sub"]
    email = userinfo["email"]
    display_name = userinfo.get("name", email.split("@")[0])

    user = await get_or_create_google_user(db, google_id=google_id, email=email, display_name=display_name)
    await db.commit()

    jwt_token = create_access_token(user.id)
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=False,
        samesite="lax",
        max_age=settings.jwt_expiration_minutes * 60,
        secure=settings.app_env != "development",
    )
    return response
