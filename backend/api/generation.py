"""Generation API routes — start pipeline, check progress per contracts/api.yaml."""

import asyncio
import logging
import os
import shutil
import subprocess
import sys
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.auth import get_current_user
from backend.api.dependencies import get_user_project
from backend.database import async_session_factory, get_db
from backend.models.project import Project, ProjectStatus
from backend.models.scenario import ModerationStatus, Scenario
from backend.models.video import ClipStatus, FinalVideo, VideoClip
from backend.schemas.auth import UserResponse
from backend.schemas.video import ClipStatusResponse, PipelineStatusResponse
from backend.services.image_gen_service import generate_initial_image
from backend.services.video_gen_service import extract_last_frame, generate_video_clip

logger = logging.getLogger(__name__)


def _log(msg: str, *args) -> None:
    """Log to both logger and stderr for visibility in background tasks."""
    formatted = msg % args if args else msg
    logger.info(formatted)
    print(f"[PIPELINE] {formatted}", file=sys.stderr, flush=True)


def _ffmpeg_exe() -> str:
    """Resolve ffmpeg path: system PATH first, then imageio_ffmpeg bundle."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"

router = APIRouter(prefix="/api/projects", tags=["Generation"])

# Base directory for generated files
GENERATED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "generated")


async def run_pipeline_background(project_id: uuid.UUID) -> None:
    """Run the full generation pipeline in the background.

    Creates VideoClip records, calls fal.ai for image + video generation,
    updates status as each clip completes, then concatenates all clips.
    Uses its own DB session since this runs outside the request lifecycle.
    """
    async with async_session_factory() as db:
        try:
            # Load project
            result = await db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()
            if not project:
                logger.error("Pipeline: project %s not found", project_id)
                return

            # Load approved scenario with segments
            result = await db.execute(
                select(Scenario)
                .options(selectinload(Scenario.segments))
                .where(
                    Scenario.project_id == project.id,
                    Scenario.moderation_status == ModerationStatus.APPROVED,
                )
            )
            scenario = result.scalar_one_or_none()
            if not scenario or not scenario.segments:
                logger.error("Pipeline: no approved scenario/segments for project %s", project_id)
                project.status = ProjectStatus.FAILED
                await db.commit()
                return

            segments = sorted(scenario.segments, key=lambda s: s.sequence_number)
            total = len(segments)
            _log("Pipeline: starting for project %s — %d segments", project_id, total)

            # Prepare output directory
            output_dir = os.path.join(GENERATED_DIR, str(project_id))
            images_dir = os.path.join(output_dir, "images")
            clips_dir = os.path.join(output_dir, "clips")
            os.makedirs(images_dir, exist_ok=True)
            os.makedirs(clips_dir, exist_ok=True)

            # Delete any existing clips from previous attempts
            existing = await db.execute(
                select(VideoClip).where(VideoClip.project_id == project.id)
            )
            for old_clip in existing.scalars().all():
                await db.delete(old_clip)
            await db.flush()

            # Create VideoClip records for all segments (status=pending)
            clip_records: list[VideoClip] = []
            for seg in segments:
                clip = VideoClip(
                    project_id=project.id,
                    segment_id=seg.id,
                    sequence_number=seg.sequence_number,
                    status=ClipStatus.PENDING,
                )
                db.add(clip)
                clip_records.append(clip)
            await db.commit()

            # Step 1: Generate initial image from first segment
            first_seg = segments[0]
            first_clip = clip_records[0]
            first_clip.status = ClipStatus.GENERATING
            await db.commit()

            _log("Pipeline [%s]: generating initial image for segment 1/%d", project_id, total)
            try:
                current_image = await generate_initial_image(
                    prompt=first_seg.description,
                    output_dir=images_dir,
                    style=project.video_style.value,
                )
                first_clip.input_image_path = current_image
                await db.commit()
                _log("Pipeline [%s]: initial image saved to %s", project_id, current_image)
            except Exception as exc:
                _log("Pipeline [%s]: initial image generation FAILED: %s", project_id, exc)
                logger.exception("Pipeline [%s]: initial image generation failed", project_id)
                first_clip.status = ClipStatus.FAILED
                first_clip.error_message = str(exc)
                project.status = ProjectStatus.FAILED
                await db.commit()
                return

            # Step 2: Generate video clips iteratively
            for i, (seg, clip) in enumerate(zip(segments, clip_records, strict=True)):
                # ── Abort check: stop if project status was changed (e.g. user abort) ──
                await db.refresh(project)
                if project.status != ProjectStatus.GENERATING:
                    _log("Pipeline [%s]: aborted — status changed to %s", project_id, project.status.value)
                    return

                seq = seg.sequence_number
                clip.status = ClipStatus.GENERATING
                clip.input_image_path = current_image
                await db.commit()

                clip_path = os.path.join(clips_dir, f"clip_{seq:03d}.mp4")
                frame_path = os.path.join(images_dir, f"last_frame_{seq:03d}.jpg")

                _log("Pipeline [%s]: generating clip %d/%d (segment %d)", project_id, i + 1, total, seq)

                # Retry logic (FR-024)
                max_retries = 1
                last_error = None
                for attempt in range(1 + max_retries):
                    try:
                        video_path = await generate_video_clip(
                            image_path=current_image,
                            prompt=seg.description,
                            output_path=clip_path,
                            style=project.video_style.value,
                        )
                        last_error = None
                        break
                    except Exception as exc:
                        last_error = exc
                        clip.retry_count = attempt + 1
                        logger.warning(
                            "Pipeline [%s]: clip %d attempt %d failed: %s",
                            project_id, seq, attempt + 1, exc,
                        )
                        if attempt < max_retries:
                            await asyncio.sleep(2)  # Brief pause before retry

                if last_error is not None:
                    logger.error("Pipeline [%s]: clip %d failed after retries", project_id, seq)
                    clip.status = ClipStatus.FAILED
                    clip.error_message = str(last_error)
                    project.status = ProjectStatus.FAILED
                    await db.commit()
                    return

                # Extract last frame for next segment
                try:
                    current_image = await extract_last_frame(
                        video_path=video_path,
                        output_path=frame_path,
                    )
                except Exception as exc:
                    logger.error("Pipeline [%s]: last frame extraction failed for clip %d: %s", project_id, seq, exc)
                    clip.status = ClipStatus.FAILED
                    clip.error_message = f"Frame extraction failed: {exc}"
                    project.status = ProjectStatus.FAILED
                    await db.commit()
                    return

                clip.status = ClipStatus.COMPLETED
                clip.video_file_path = video_path
                clip.last_frame_path = current_image
                clip.duration = 5.0  # ~5 seconds at 121 frames / 24fps
                clip.generation_cost = 0.04  # $0.04 per clip
                await db.commit()
                _log("Pipeline [%s]: clip %d/%d completed", project_id, i + 1, total)

            # Step 3: Concatenate all clips
            _log("Pipeline [%s]: concatenating %d clips", project_id, total)
            project.status = ProjectStatus.CONCATENATING
            await db.commit()

            try:
                final_path = await concatenate_clips(clips_dir, output_dir, total)
            except Exception:
                logger.exception("Pipeline [%s]: concatenation failed", project_id)
                project.status = ProjectStatus.FAILED
                await db.commit()
                return

            # Create FinalVideo record
            file_size = os.path.getsize(final_path) if os.path.exists(final_path) else 0
            total_duration = total * 5.0
            total_cost = total * 0.04 + 0.02  # clips + initial image

            final_video = FinalVideo(
                project_id=project.id,
                file_path=final_path,
                total_duration=total_duration,
                total_cost=total_cost,
                file_size=file_size,
            )
            db.add(final_video)
            project.status = ProjectStatus.COMPLETED
            project.actual_cost = total_cost
            await db.commit()
            _log("Pipeline [%s]: COMPLETED! Final video at %s", project_id, final_path)

        except Exception as exc:
            _log("Pipeline [%s]: UNEXPECTED ERROR: %s", project_id, exc)
            logger.exception("Pipeline [%s]: unexpected error", project_id)
            try:
                project.status = ProjectStatus.FAILED
                await db.commit()
            except Exception:
                await db.rollback()


async def concatenate_clips(clips_dir: str, output_dir: str, total_clips: int) -> str:
    """Concatenate all clips using ffmpeg concat demuxer.

    Creates a file list and runs ffmpeg -f concat to merge all clips.
    Runs ffmpeg in a thread to avoid blocking the async event loop.
    """
    # Create concat file list
    list_path = os.path.join(output_dir, "concat_list.txt")
    with open(list_path, "w") as f:
        for i in range(1, total_clips + 1):
            clip_path = os.path.join(clips_dir, f"clip_{i:03d}.mp4")
            f.write(f"file '{clip_path}'\n")

    final_path = os.path.join(output_dir, "final_video.mp4")

    ffmpeg = _ffmpeg_exe()
    result = await asyncio.to_thread(
        subprocess.run,
        [
            ffmpeg,
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            "-y",
            final_path,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed: {result.stderr}")

    return final_path


@router.post(
    "/{project_id}/generate",
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_generation(
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
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

    # Transition project status to generating — commit before background task
    # so the background task's separate DB session sees the new status.
    project.status = ProjectStatus.GENERATING
    await db.commit()

    # Launch pipeline in background
    background_tasks.add_task(run_pipeline_background, project.id)
    _log("Pipeline launched in background for project %s", project.id)

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
    completed_count = 0
    failed_count = 0
    for clip in clips:
        if clip.status == ClipStatus.GENERATING:
            current_segment = clip.sequence_number
        elif clip.status == ClipStatus.COMPLETED:
            completed_count += 1
        elif clip.status == ClipStatus.FAILED:
            failed_count += 1

    # Count total segments from scenario
    scenario_result = await db.execute(
        select(Scenario)
        .options(selectinload(Scenario.segments))
        .where(Scenario.project_id == project.id)
    )
    scenario = scenario_result.scalar_one_or_none()
    total_segments = len(scenario.segments) if scenario else None

    # Build human-readable status message
    proj_status = project.status.value
    if proj_status == "generating":
        if not clips:
            message = "Initializing pipeline — creating clip records..."
        elif current_segment is not None:
            message = f"Generating clip {current_segment} of {total_segments or '?'}... ({completed_count} completed)"
        else:
            message = f"Preparing next clip... ({completed_count} of {total_segments or '?'} completed)"
    elif proj_status == "concatenating":
        message = f"All {total_segments} clips generated! Concatenating into final video..."
    elif proj_status == "completed":
        message = f"Done! {total_segments} clips generated and merged into final video."
    elif proj_status == "failed":
        if failed_count > 0:
            failed_clip = next((c for c in clips if c.status == ClipStatus.FAILED), None)
            err = failed_clip.error_message if failed_clip else "Unknown error"
            message = f"Generation failed at clip {failed_clip.sequence_number if failed_clip else '?'}: {err}"
        else:
            message = "Generation failed. Please try again."
    else:
        message = f"Status: {proj_status}"

    # Check for final video URL
    final_video_url = None
    if proj_status == "completed":
        fv_result = await db.execute(
            select(FinalVideo).where(FinalVideo.project_id == project.id)
        )
        fv = fv_result.scalar_one_or_none()
        if fv and fv.file_path:
            # Convert file path to URL: generated/{project_id}/final_video.mp4
            final_video_url = f"/generated/{project_id}/final_video.mp4"

    return PipelineStatusResponse(
        project_id=project.id,
        status=proj_status,
        current_segment=current_segment,
        total_segments=total_segments,
        completed_segments=completed_count,
        failed_segments=failed_count,
        message=message,
        clips=[ClipStatusResponse.model_validate(c) for c in clips],
        final_video_url=final_video_url,
    )


@router.post(
    "/{project_id}/abort",
    status_code=status.HTTP_200_OK,
)
async def abort_generation(
    project_id: uuid.UUID,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Abort a running generation pipeline.

    Resets the project status to REVIEWING so generation can be re-triggered.
    The background task will detect the status change and stop on its next check.
    """
    project = await get_user_project(project_id, current_user.id, db, load_persons=False)

    if project.status not in (ProjectStatus.GENERATING, ProjectStatus.CONCATENATING, ProjectStatus.FAILED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot abort project in '{project.status.value}' state.",
        )

    _log("Aborting generation for project %s (was %s)", project_id, project.status.value)

    # Reset project status to REVIEWING (segments are still intact)
    project.status = ProjectStatus.REVIEWING

    # Delete incomplete clip records
    existing = await db.execute(
        select(VideoClip).where(VideoClip.project_id == project.id)
    )
    for clip in existing.scalars().all():
        await db.delete(clip)

    # Delete any final video record
    fv_result = await db.execute(
        select(FinalVideo).where(FinalVideo.project_id == project.id)
    )
    for fv in fv_result.scalars().all():
        await db.delete(fv)

    await db.commit()
    return {"status": "aborted", "project_id": str(project.id)}
