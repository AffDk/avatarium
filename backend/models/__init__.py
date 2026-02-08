"""SQLAlchemy declarative base and model registry."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


# Import all models so Alembic and create_all can discover them.
# These imports MUST remain at the bottom to avoid circular imports.
from backend.models.user import User  # noqa: E402, F401
