"""Generation API routes — start / status / abort pipeline."""

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.auth import get_current_user
from backend.api.dependencies import get_user_project
from backend.database import get_db
from backend.models.project import ProjectStatus
from backend.models.scenario import ModerationStatus, Scenario
from backend.models.video import ClipStatus, FinalVideo, VideoClip
from backend.schemas.auth import UserResponse
from backend.schemas.video import ClipStatusResponse, PipelineStatusResponse
from backend.services.pipeline_service import run_pipeline_background

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["Generation"])


# ── Start ──────────────────────────────────────────────────────────────


@router.post("/{project_id}/generate", status_code=status.HTTP_202_ACCEPTED)
async def start_generation(
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Launch the video generation pipeline (202 Accepted)."""
    project = await get_user_project(project_id, current_user.id, db, load_persons=False)

    # Must have an approved scenario
    scenario = (await db.execute(
        select(Scenario).options(selectinload(Scenario.segments))
        .where(Scenario.project_id == project.id,
               Scenario.moderation_status == ModerationStatus.APPROVED)
    )).scalar_one_or_none()

    if scenario is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail="No approved scenario found.")

    if project.status in (ProjectStatus.GENERATING, ProjectStatus.CONCATENATING):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail="Pipeline is already running.")

    project.status = ProjectStatus.GENERATING
    await db.commit()

    background_tasks.add_task(run_pipeline_background, project.id)
    logger.info("Pipeline launched for project %s", project.id)
    return {"status": "generating", "project_id": str(project.id)}


# ── Status ─────────────────────────────────────────────────────────────


def _build_status_message(
    proj_status: str, clips: list, total: int | None,
    current_seg: int | None, done: int, failed: int,
) -> str:
    if proj_status == "generating":
        if not clips:
            return "Initializing pipeline — loading project data..."
        # Check if any clip is actively generating
        generating_clip = next((c for c in clips if c.status == ClipStatus.GENERATING), None)
        if done == 0 and generating_clip and generating_clip.sequence_number == 1:
            return (
                "Generating initial reference image — "
                "uploading photos & waiting in fal.ai queue..."
            )
        if current_seg is not None:
            return (
                f"Generating clip {current_seg}/{total or '?'} "
                f"({done} completed) — rendering on fal.ai..."
            )
        return f"Preparing next clip ({done}/{total or '?'} done)"
    if proj_status == "concatenating":
        return f"All {total} clips rendered — stitching final video with ffmpeg..."
    if proj_status == "completed":
        return f"Done! {total} clips merged into final video."
    if proj_status == "failed":
        if failed:
            bad = next((c for c in clips if c.status == ClipStatus.FAILED), None)
            err = bad.error_message if bad else "Unknown"
            return f"Failed at clip {bad.sequence_number if bad else '?'}: {err}"
        return "Generation failed. Please try again."
    return f"Status: {proj_status}"


@router.get("/{project_id}/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    project_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PipelineStatusResponse:
    """Return current pipeline progress with per-clip details."""
    project = await get_user_project(project_id, current_user.id, db, load_persons=False)

    clips = (await db.execute(
        select(VideoClip).where(VideoClip.project_id == project.id)
        .order_by(VideoClip.sequence_number)
    )).scalars().all()

    current_segment = None
    completed = failed = 0
    for c in clips:
        if c.status == ClipStatus.GENERATING:
            current_segment = c.sequence_number
        elif c.status == ClipStatus.COMPLETED:
            completed += 1
        elif c.status == ClipStatus.FAILED:
            failed += 1

    scenario = (await db.execute(
        select(Scenario).options(selectinload(Scenario.segments))
        .where(Scenario.project_id == project.id)
    )).scalar_one_or_none()
    total_segments = len(scenario.segments) if scenario else None

    proj_status = project.status.value
    message = _build_status_message(
        proj_status, list(clips), total_segments, current_segment, completed, failed,
    )

    final_video_url = None
    if proj_status == "completed":
        fv = (await db.execute(
            select(FinalVideo).where(FinalVideo.project_id == project.id)
        )).scalar_one_or_none()
        if fv and fv.file_path:
            final_video_url = f"/generated/{project_id}/final_video.mp4"

    return PipelineStatusResponse(
        project_id=project.id,
        status=proj_status,
        current_segment=current_segment,
        total_segments=total_segments,
        completed_segments=completed,
        failed_segments=failed,
        message=message,
        clips=[ClipStatusResponse.model_validate(c) for c in clips],
        final_video_url=final_video_url,
    )


# ── Abort ──────────────────────────────────────────────────────────────


@router.post("/{project_id}/abort", status_code=status.HTTP_200_OK)
async def abort_generation(
    project_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Abort a running pipeline and reset to REVIEWING."""
    project = await get_user_project(project_id, current_user.id, db, load_persons=False)

    allowed = {ProjectStatus.GENERATING, ProjectStatus.CONCATENATING, ProjectStatus.FAILED}
    if project.status not in allowed:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail=f"Cannot abort in '{project.status.value}' state.")

    logger.info("Aborting project %s (was %s)", project_id, project.status.value)
    project.status = ProjectStatus.REVIEWING

    for clip in (await db.execute(
        select(VideoClip).where(VideoClip.project_id == project.id)
    )).scalars().all():
        await db.delete(clip)

    for fv in (await db.execute(
        select(FinalVideo).where(FinalVideo.project_id == project.id)
    )).scalars().all():
        await db.delete(fv)

    await db.commit()
    return {"status": "aborted", "project_id": str(project.id)}
