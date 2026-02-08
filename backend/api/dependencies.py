"""Shared API dependencies — common helpers used across routers."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.project import Person, Project


async def get_user_project(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    *,
    load_persons: bool = True,
) -> Project:
    """Fetch a project ensuring it belongs to the given user.

    Args:
        project_id: The project UUID.
        user_id: The authenticated user's UUID.
        db: Async database session.
        load_persons: Whether to eagerly load persons and photos (default True).

    Raises:
        HTTPException 404: If the project doesn't exist or doesn't belong to the user.
    """
    query = select(Project).where(
        Project.id == project_id, Project.user_id == user_id
    )
    if load_persons:
        query = query.options(
            selectinload(Project.persons).selectinload(Person.photos)
        )

    result = await db.execute(query)
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project
