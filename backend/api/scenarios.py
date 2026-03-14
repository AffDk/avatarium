"""Scenario API routes — submit, moderate, get per contracts/api.yaml."""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.auth import get_current_user
from backend.api.dependencies import get_user_project
from backend.database import get_db
from backend.models.project import Project
from backend.models.scenario import ModerationStatus, Scenario, Segment
from backend.schemas.auth import UserResponse
from backend.schemas.scenario import (
    ScenarioDetailResponse,
    SegmentResponse,
    SubmitScenarioRequest,
)
from backend.services.moderation_service import moderate_and_split

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["Scenarios"])


@router.put("/{project_id}/scenario", response_model=ScenarioDetailResponse)
async def submit_scenario(
    project_id: uuid.UUID,
    body: SubmitScenarioRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScenarioDetailResponse:
    """Submit or re-submit a scenario. Triggers moderation + splitting via Gemini."""
    project = await get_user_project(project_id, current_user.id, db, load_persons=True)

    # Extract person names for person-aware splitting
    person_names = [p.name for p in project.persons] if project.persons else []

    # Collect photo file paths for multimodal Gemini analysis
    photo_paths: dict[str, list[str]] = {}
    if project.persons:
        for person in project.persons:
            paths = [photo.file_path for photo in person.photos if photo.file_path]
            if paths:
                photo_paths[person.name] = paths

    # Check if scenario already exists — if so, delete old one for re-submission
    result = await db.execute(
        select(Scenario)
        .options(selectinload(Scenario.segments))
        .where(Scenario.project_id == project.id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        await db.delete(existing)
        await db.flush()

    # Call Gemini for moderation + splitting
    try:
        gemini_result = await moderate_and_split(
            body.text, person_names=person_names, photo_paths=photo_paths or None,
        )
    except Exception as exc:
        logger.exception("Gemini moderation failed for project %s", project_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI moderation service error: {exc}",
        ) from exc

    # Create scenario record
    moderation_status = (
        ModerationStatus.APPROVED if gemini_result["approved"] else ModerationStatus.REJECTED
    )
    scenario = Scenario(
        project_id=project.id,
        text=body.text,
        moderation_status=moderation_status,
        rejection_reason=gemini_result.get("rejection_reason"),
        moderated_at=datetime.now(UTC),
    )
    db.add(scenario)
    await db.flush()

    # Create segment records if approved
    segments: list[Segment] = []
    if gemini_result["approved"]:
        for seg_data in gemini_result["segments"]:
            segment = Segment(
                scenario_id=scenario.id,
                sequence_number=seg_data["sequence_number"],
                description=seg_data["description"],
                persons=seg_data.get("persons", []),
            )
            db.add(segment)
            segments.append(segment)
        await db.flush()

    return ScenarioDetailResponse(
        id=scenario.id,
        text=scenario.text,
        moderation_status=scenario.moderation_status.value,
        rejection_reason=scenario.rejection_reason,
        created_at=scenario.created_at,
        moderated_at=scenario.moderated_at,
        segments=[SegmentResponse.model_validate(s) for s in segments],
    )


@router.get("/{project_id}/scenario", response_model=ScenarioDetailResponse)
async def get_scenario(
    project_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScenarioDetailResponse:
    """Get scenario with moderation status and segments."""
    project = await get_user_project(project_id, current_user.id, db, load_persons=False)

    result = await db.execute(
        select(Scenario)
        .options(selectinload(Scenario.segments))
        .where(Scenario.project_id == project.id)
    )
    scenario = result.scalar_one_or_none()
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No scenario submitted"
        )

    return ScenarioDetailResponse(
        id=scenario.id,
        text=scenario.text,
        moderation_status=scenario.moderation_status.value,
        rejection_reason=scenario.rejection_reason,
        created_at=scenario.created_at,
        moderated_at=scenario.moderated_at,
        segments=[SegmentResponse.model_validate(s) for s in scenario.segments],
    )
