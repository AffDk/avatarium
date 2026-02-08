"""Video pipeline Pydantic v2 schemas per contracts/api.yaml."""

import uuid

from datetime import datetime
from pydantic import BaseModel


class ClipStatusResponse(BaseModel):
    """Individual clip status."""

    id: uuid.UUID
    sequence_number: int
    status: str
    retry_count: int
    error_message: str | None = None

    model_config = {"from_attributes": True}


class PipelineStatusResponse(BaseModel):
    """Pipeline status with per-segment progress."""

    project_id: uuid.UUID
    status: str
    current_segment: int | None = None
    total_segments: int | None = None
    clips: list[ClipStatusResponse] = []
    estimated_cost: float | None = None


class FinalVideoResponse(BaseModel):
    """Final concatenated video metadata."""

    id: uuid.UUID
    total_duration: float
    total_cost: float
    file_size: int
    created_at: datetime

    model_config = {"from_attributes": True}
