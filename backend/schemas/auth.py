"""Auth request/response schemas per contracts/api.yaml."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """POST /api/auth/register request body."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    """POST /api/auth/login request body."""

    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    """Successful auth response with JWT token."""

    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    """Public user representation."""

    id: uuid.UUID
    email: str
    display_name: str
    email_verified: bool
    terms_accepted_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
