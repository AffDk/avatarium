"""Scenario and Segment models per data-model.md."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models import Base


class ModerationStatus(str, enum.Enum):
    """Scenario moderation status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class GenerationStatus(str, enum.Enum):
    """Per-segment generation status."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class Scenario(Base):
    """A scenario submitted for a project, with moderation state."""

    __tablename__ = "scenarios"

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
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    moderation_status: Mapped[ModerationStatus] = mapped_column(
        Enum(ModerationStatus),
        nullable=False,
        default=ModerationStatus.PENDING,
    )
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    moderated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    segments: Mapped[list["Segment"]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Segment.sequence_number",
    )


class Segment(Base):
    """A single segment (~5 sec) of the scenario."""

    __tablename__ = "segments"
    __table_args__ = (
        UniqueConstraint("scenario_id", "sequence_number", name="uq_segment_scenario_seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    persons: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        doc="Person names appearing in this segment (lowercase).",
    )
    estimated_duration: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=5.0,
    )
    generation_status: Mapped[GenerationStatus] = mapped_column(
        Enum(GenerationStatus),
        nullable=False,
        default=GenerationStatus.PENDING,
    )

    # Relationships
    scenario: Mapped["Scenario"] = relationship(back_populates="segments")
