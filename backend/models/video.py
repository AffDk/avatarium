"""VideoClip and FinalVideo models per data-model.md."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models import Base


class ClipStatus(str, enum.Enum):
    """Video clip generation status."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoClip(Base):
    """An individual generated video clip for one segment."""

    __tablename__ = "video_clips"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    segment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("segments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    input_image_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    video_file_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    last_frame_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    duration: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    generation_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4),
        nullable=True,
    )
    status: Mapped[ClipStatus] = mapped_column(
        Enum(ClipStatus),
        nullable=False,
        default=ClipStatus.PENDING,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class FinalVideo(Base):
    """The concatenated final video for a project."""

    __tablename__ = "final_videos"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    total_duration: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(6, 4),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
