"""Project, Person, and Photo models per data-model.md."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models import Base


class VideoStyle(str, enum.Enum):
    """Video style options."""

    ANIMATION = "animation"
    MOVIE_LIKE = "movie_like"


class ProjectStatus(str, enum.Enum):
    """Project lifecycle status."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    MODERATING = "moderating"
    SPLITTING = "splitting"
    REVIEWING = "reviewing"
    GENERATING = "generating"
    CONCATENATING = "concatenating"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class Project(Base):
    """A video generation project owned by a user."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    video_style: Mapped[VideoStyle] = mapped_column(
        Enum(VideoStyle),
        nullable=False,
    )
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus),
        nullable=False,
        default=ProjectStatus.DRAFT,
    )
    estimated_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4),
        nullable=True,
    )
    actual_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 4),
        nullable=True,
    )
    video_resolution: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        default="480p",
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

    # Relationships
    persons: Mapped[list["Person"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Person(Base):
    """A named person derived from uploaded photo filenames."""

    __tablename__ = "persons"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_person_project_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="persons")
    photos: Mapped[list["Photo"]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Photo(Base):
    """An uploaded reference photo for a person."""

    __tablename__ = "photos"
    __table_args__ = (
        UniqueConstraint("person_id", "sequence_number", name="uq_photo_person_seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    person: Mapped["Person"] = relationship(back_populates="photos")
