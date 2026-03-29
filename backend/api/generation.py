"""Generation API routes — start / status / abort pipeline."""

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.auth import get_current_user
from backend.api.dependencies import get_user_project
from backend.config import settings
from backend.database import get_db
from backend.models.project import ProjectStatus
from backend.models.scenario import ModerationStatus, Scenario
from backend.models.video import ClipStatus, FinalVideo, VideoClip
from backend.schemas.auth import UserResponse
from backend.schemas.video import ClipStatusResponse, PipelineStatusResponse
from backend.services.pipeline_service import CLIP_COST, IMAGE_COST, run_pipeline_background

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["Generation"])

# Cost multipliers per resolution relative to 480p baseline
_RESOLUTION_COST_MULTIPLIERS: dict[str, tuple[float, float]] = {
    # resolution: (low_multiplier, high_multiplier)
    "480p": (1.0, 1.0),
    "720p": (2.0, 2.5),
}
_VALID_RESOLUTIONS = frozenset(_RESOLUTION_COST_MULTIPLIERS.keys())

# Baseline per-clip cost range at 480p (fal.ai GPU-time estimate)
_CLIP_COST_LOW_480P = 0.02
_CLIP_COST_HIGH_480P = 0.05
# Per-image cost range (Qwen image, landscape_16_9)
_IMAGE_COST_LOW = 0.01
_IMAGE_COST_HIGH = 0.03


class GenerateRequest(BaseModel):
    """Optional request body for POST /generate."""

    video_resolution: str = "480p"

    @field_validator("video_resolution")
    @classmethod
    def validate_resolution(cls, v: str) -> str:
        if v not in _VALID_RESOLUTIONS:
            raise ValueError(f"Must be one of: {', '.join(sorted(_VALID_RESOLUTIONS))}")
        return v


# ── Cost estimate ─────────────────────────────────────────────────────


@router.get("/{project_id}/cost-estimate")
async def get_cost_estimate(
    project_id: uuid.UUID,
    resolution: str = "480p",
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a low/high cost estimate for generating this project."""
    if resolution not in _VALID_RESOLUTIONS:
        resolution = "480p"

    project = await get_user_project(project_id, current_user.id, db, load_persons=False)

    scenario = (await db.execute(
        select(Scenario).options(selectinload(Scenario.segments))
        .where(Scenario.project_id == project.id,
               Scenario.moderation_status == ModerationStatus.APPROVED)
    )).scalar_one_or_none()

    n_clips = len(scenario.segments) if scenario else 0

    low_mult, high_mult = _RESOLUTION_COST_MULTIPLIERS[resolution]
    clip_low = _CLIP_COST_LOW_480P * low_mult
    clip_high = _CLIP_COST_HIGH_480P * high_mult
    img_low = _IMAGE_COST_LOW
    img_high = _IMAGE_COST_HIGH

    # 1 initial image + up to 1 transition image per clip (average ~50% chance)
    # Conservative estimate: count 1 image minimum, +1 if >1 clip
    n_images_min = 1
    n_images_max = 2 if n_clips > 1 else 1

    total_low = round(n_clips * clip_low + n_images_min * img_low, 3)
    total_high = round(n_clips * clip_high + n_images_max * img_high, 3)

    return {
        "resolution": resolution,
        "n_clips": n_clips,
        "per_clip_low": round(clip_low, 3),
        "per_clip_high": round(clip_high, 3),
        "per_image_low": img_low,
        "per_image_high": img_high,
        "total_low": total_low,
        "total_high": total_high,
        "video_model": settings.fal_video_model,
        "image_model": settings.fal_image_model,
        "note": (
            "Estimates based on fal.ai GPU-compute time (~$0.0005/s on H100). "
            "Actual charges may vary with queue wait times excluded."
        ),
    }


# ── Start ──────────────────────────────────────────────────────────────


@router.post("/{project_id}/generate", status_code=status.HTTP_202_ACCEPTED)
async def start_generation(
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    body: GenerateRequest = GenerateRequest(),  # noqa: B008
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
    project.video_resolution = body.video_resolution
    await db.commit()

    background_tasks.add_task(run_pipeline_background, project.id)
    logger.info("Pipeline launched for project %s (resolution=%s)", project.id, body.video_resolution)
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
