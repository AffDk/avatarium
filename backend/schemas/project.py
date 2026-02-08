"""Project, Person, and Photo Pydantic v2 schemas per contracts/api.yaml."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from backend.models.project import VideoStyle


class CreateProjectRequest(BaseModel):
    """POST /api/projects request body."""

    title: str = Field(min_length=1, max_length=200)
    video_style: VideoStyle


class ProjectResponse(BaseModel):
    """Single project representation."""

    id: uuid.UUID
    title: str
    video_style: VideoStyle
    status: str
    estimated_cost: float | None = None
    actual_cost: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PersonResponse(BaseModel):
    """Person with photo count."""

    id: uuid.UUID
    name: str
    photo_count: int = 0

    model_config = {"from_attributes": True}


class ProjectDetailResponse(ProjectResponse):
    """Project with nested persons and scenario info."""

    persons: list[PersonResponse] = []
    scenario: dict | None = None  # Will be ScenarioResponse in Phase 4
    final_video: dict | None = None  # Will be FinalVideoResponse in Phase 6


class ProjectListResponse(BaseModel):
    """Paginated project list."""

    items: list[ProjectResponse]
    page: int
    per_page: int
    total: int


class PhotoResponse(BaseModel):
    """Single photo representation."""

    id: uuid.UUID
    original_filename: str
    sequence_number: int
    file_size: int
    mime_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PhotoGroupResponse(BaseModel):
    """Photos grouped by person."""

    persons: list[dict]  # [{person: PersonResponse, photos: [PhotoResponse]}]


class PhotoUploadResponse(BaseModel):
    """Response after uploading photos."""

    uploaded: int
    persons_created: list[str]
    photos: list[PhotoResponse]
