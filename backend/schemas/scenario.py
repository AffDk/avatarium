"""Scenario and Segment Pydantic v2 schemas per contracts/api.yaml."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SubmitScenarioRequest(BaseModel):
    """PUT /api/projects/{id}/scenario request body."""

    text: str = Field(min_length=1, max_length=10000)


class SegmentResponse(BaseModel):
    """Single segment representation."""

    id: uuid.UUID
    sequence_number: int
    description: str
    persons: list[str] = []
    estimated_duration: float
    generation_status: str

    model_config = {"from_attributes": True}


class ScenarioResponse(BaseModel):
    """Scenario with moderation status (without segments)."""

    id: uuid.UUID
    text: str
    moderation_status: str
    rejection_reason: str | None = None
    created_at: datetime
    moderated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ScenarioDetailResponse(ScenarioResponse):
    """Scenario with moderation status and segments."""

    segments: list[SegmentResponse] = []
