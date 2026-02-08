"""Generation API routes — start pipeline, check progress per contracts/api.yaml."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.auth import get_current_user
from backend.api.dependencies import get_user_project
from backend.database import get_db
from backend.models.project import ProjectStatus
from backend.models.scenario import ModerationStatus, Scenario
from backend.models.video import ClipStatus, VideoClip
from backend.schemas.auth import UserResponse
from backend.schemas.video import ClipStatusResponse, PipelineStatusResponse

router = APIRouter(prefix="/api/projects", tags=["Generation"])


async def launch_pipeline(
    project_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Launch the video generation pipeline as a background task.

    This is a placeholder that will be wired to BackgroundTasks or a task queue.
    Separated for easy mocking in tests.
    """
    # In production this would kick off pipeline_service.run_pipeline
    # via BackgroundTasks or Celery/ARQ.
    pass


@router.post(
    "/{project_id}/generate",
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_generation(
    project_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Start the video generation pipeline for a project.

    Returns 202 Accepted if the pipeline is launched.
    Returns 400 if no approved scenario exists.
    Returns 409 if the pipeline is already running.
    """
    project = await get_user_project(project_id, current_user.id, db, load_persons=False)

    # Check for approved scenario
    result = await db.execute(
        select(Scenario)
        .options(selectinload(Scenario.segments))
        .where(
            Scenario.project_id == project.id,
            Scenario.moderation_status == ModerationStatus.APPROVED,
        )
    )
    scenario = result.scalar_one_or_none()
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No approved scenario found. Submit and get a scenario approved first.",
        )

    # Check if pipeline is already running (409 Conflict)
    if project.status in (ProjectStatus.GENERATING, ProjectStatus.CONCATENATING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pipeline is already running for this project.",
        )

    # Transition project status to generating
    project.status = ProjectStatus.GENERATING
    await db.flush()

    # Launch pipeline (mocked in tests)
    await launch_pipeline(project.id, db)

    return {"status": "generating", "project_id": str(project.id)}


@router.get(
    "/{project_id}/status",
    response_model=PipelineStatusResponse,
)
async def get_pipeline_status(
    project_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PipelineStatusResponse:
    """Get current pipeline status with per-segment progress."""
    project = await get_user_project(project_id, current_user.id, db, load_persons=False)

    # Fetch video clips for this project
    result = await db.execute(
        select(VideoClip)
        .where(VideoClip.project_id == project.id)
        .order_by(VideoClip.sequence_number)
    )
    clips = result.scalars().all()

    # Determine current segment being generated
    current_segment = None
    for clip in clips:
        if clip.status == ClipStatus.GENERATING:
            current_segment = clip.sequence_number
            break

    # Count total segments from scenario
    scenario_result = await db.execute(
        select(Scenario)
        .options(selectinload(Scenario.segments))
        .where(Scenario.project_id == project.id)
    )
    scenario = scenario_result.scalar_one_or_none()
    total_segments = len(scenario.segments) if scenario else None

    return PipelineStatusResponse(
        project_id=project.id,
        status=project.status.value,
        current_segment=current_segment,
        total_segments=total_segments,
        clips=[ClipStatusResponse.model_validate(c) for c in clips],
    )
