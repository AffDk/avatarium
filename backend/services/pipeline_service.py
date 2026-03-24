"""Pipeline orchestration — iterative video generation with DB status tracking.

1. Collect reference photos from uploaded person images
2. Generate initial image from first segment + reference photos
3. For each segment: generate video clip → extract last frame → chain
4. Concatenate all clips into final video via ffmpeg
5. Retry failed clips once (FR-024)
"""

import asyncio
import logging
import os
import subprocess
import sys
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.database import async_session_factory
from backend.models.project import Person, Project, ProjectStatus
from backend.models.scenario import ModerationStatus, Scenario
from backend.models.video import ClipStatus, FinalVideo, VideoClip
from backend.services._utils import ffmpeg_exe
from backend.services.image_gen_service import (
    generate_initial_image,
    generate_transition_image,
)
from backend.services.video_gen_service import extract_last_frame, generate_video_clip

logger = logging.getLogger(__name__)

MAX_RETRIES = 1  # FR-024
CLIP_DURATION = 5.0  # ~5 s at 121 frames / 24 fps
CLIP_COST = 0.04
IMAGE_COST = 0.02

GENERATED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "generated",
)


def _log(msg: str, *args: object) -> None:
    """Write to both the logger and stderr (background tasks have no console)."""
    formatted = msg % args if args else msg
    logger.info(formatted)
    print(f"[PIPELINE] {formatted}", file=sys.stderr, flush=True)


# ── helpers ────────────────────────────────────────────────────────────


def _collect_reference_photos(
    persons: list[Person], project_id: uuid.UUID,
) -> dict[str, str]:
    """Return a mapping of person name (lowercase) → best photo path.

    Picks the first photo (lowest sequence_number) per person, skipping missing files.
    """
    mapping: dict[str, str] = {}
    for person in persons:
        if not person.photos:
            continue
        best = min(person.photos, key=lambda p: p.sequence_number)
        if os.path.exists(best.file_path):
            mapping[person.name.lower()] = best.file_path
            _log("Pipeline [%s]: ref photo for '%s': %s", project_id, person.name, best.file_path)
        else:
            logger.warning("Pipeline [%s]: ref photo missing for '%s': %s",
                           project_id, person.name, best.file_path)
    return mapping


def _get_segment_ref_photos(
    segment_persons: list[str],
    person_photo_map: dict[str, str],
) -> list[str]:
    """Return the list of reference photo paths for persons in a given segment."""
    paths: list[str] = []
    for name in segment_persons:
        path = person_photo_map.get(name.lower())
        if path:
            paths.append(path)
    return paths


async def _concatenate_clips(clips_dir: str, output_dir: str, total: int) -> str:
    """Concatenate clips via ffmpeg concat demuxer. Returns final video path."""
    list_path = os.path.join(output_dir, "concat_list.txt")
    with open(list_path, "w") as f:
        for i in range(1, total + 1):
            f.write(f"file '{os.path.join(clips_dir, f'clip_{i:03d}.mp4')}'\n")

    final_path = os.path.join(output_dir, "final_video.mp4")
    result = await asyncio.to_thread(
        subprocess.run,
        [ffmpeg_exe(), "-f", "concat", "-safe", "0",
         "-i", list_path, "-c", "copy", "-y", final_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed: {result.stderr}")
    return final_path


async def _fail(project: Project, db: AsyncSession, clip: VideoClip | None = None,
                error: str | None = None) -> None:
    """Mark project (and optionally a clip) as FAILED and commit."""
    if clip:
        clip.status = ClipStatus.FAILED
        clip.error_message = error
    project.status = ProjectStatus.FAILED
    await db.commit()


# ── public entry point ─────────────────────────────────────────────────


async def run_pipeline_background(project_id: uuid.UUID) -> None:
    """Run the full generation pipeline as a background task.

    Owns its own DB session since it runs outside the request lifecycle.
    """
    async with async_session_factory() as db:
        try:
            await _run(project_id, db)
        except Exception as exc:
            _log("Pipeline [%s]: UNEXPECTED ERROR: %s", project_id, exc)
            logger.exception("Pipeline [%s]: unexpected error", project_id)
            try:
                project = (await db.execute(
                    select(Project).where(Project.id == project_id)
                )).scalar_one_or_none()
                if project:
                    project.status = ProjectStatus.FAILED
                    await db.commit()
            except Exception:
                await db.rollback()


async def _run(project_id: uuid.UUID, db: AsyncSession) -> None:  # noqa: C901
    # ── load project ───────────────────────────────────────────────
    project = (await db.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one_or_none()
    if not project:
        logger.error("Pipeline: project %s not found", project_id)
        return

    # ── load approved scenario + segments ──────────────────────────
    scenario = (await db.execute(
        select(Scenario)
        .options(selectinload(Scenario.segments))
        .where(Scenario.project_id == project.id,
               Scenario.moderation_status == ModerationStatus.APPROVED)
    )).scalar_one_or_none()

    if not scenario or not scenario.segments:
        logger.error("Pipeline: no approved scenario for project %s", project_id)
        project.status = ProjectStatus.FAILED
        await db.commit()
        return

    segments = sorted(scenario.segments, key=lambda s: s.sequence_number)
    total = len(segments)
    pipeline_start = time.monotonic()
    _log("Pipeline [%s]: starting — %d segments, estimated time ~%d–%d min",
         project_id, total, total * 1, total * 2)

    # ── load reference photos ────────────────────────────────────────
    persons = (await db.execute(
        select(Person).options(selectinload(Person.photos))
        .where(Person.project_id == project.id)
    )).scalars().all()

    person_photo_map = _collect_reference_photos(list(persons), project_id)
    _log("Pipeline [%s]: collected %d reference photo(s)", project_id, len(person_photo_map))

    # ── prepare directories ────────────────────────────────────────
    output_dir = os.path.join(GENERATED_DIR, str(project_id))
    images_dir = os.path.join(output_dir, "images")
    clips_dir = os.path.join(output_dir, "clips")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(clips_dir, exist_ok=True)

    # ── reset old clips & final video ─────────────────────────────
    for old in (await db.execute(
        select(VideoClip).where(VideoClip.project_id == project.id)
    )).scalars().all():
        await db.delete(old)
    old_final = (await db.execute(
        select(FinalVideo).where(FinalVideo.project_id == project.id)
    )).scalar_one_or_none()
    if old_final:
        await db.delete(old_final)
    await db.flush()

    # ── clean stale images from previous runs ─────────────────────
    for stale in os.listdir(images_dir):
        stale_path = os.path.join(images_dir, stale)
        if os.path.isfile(stale_path):
            os.remove(stale_path)

    # ── create clip records ────────────────────────────────────────
    clips: list[VideoClip] = []
    for seg in segments:
        clip = VideoClip(project_id=project.id, segment_id=seg.id,
                         sequence_number=seg.sequence_number, status=ClipStatus.PENDING)
        db.add(clip)
        clips.append(clip)
    await db.commit()

    # ── step 1: initial image ──────────────────────────────────────
    clips[0].status = ClipStatus.GENERATING
    await db.commit()
    _log("Pipeline [%s]: STEP 1/3 — generating initial reference image "
         "(model: %s, uploading ref photos + fal.ai queue, may take 30–90s)...",
         project_id, settings.fal_image_model)
    img_start = time.monotonic()

    # Use ALL persons' reference photos for the initial image,
    # not just those in segment 1, so the model sees every character.
    first_seg_ref_photos = list(person_photo_map.values())
    _log("Pipeline [%s]: initial image uses %d person ref photo(s): %s",
         project_id, len(first_seg_ref_photos),
         [os.path.basename(p) for p in first_seg_ref_photos])

    try:
        current_image = await generate_initial_image(
            prompt=segments[0].description,
            output_dir=images_dir,
            style=project.video_style.value,
            reference_image_paths=first_seg_ref_photos or None,
        )
        clips[0].input_image_path = current_image
        await db.commit()
        _log("Pipeline [%s]: initial image ready (%.1fs)", project_id,
             time.monotonic() - img_start)
    except Exception as exc:
        _log("Pipeline [%s]: initial image FAILED after %.1fs: %s",
             project_id, time.monotonic() - img_start, exc)
        await _fail(project, db, clips[0], str(exc))
        return

    # ── step 2: iterative clip generation ──────────────────────────
    _log("Pipeline [%s]: STEP 2/3 — generating %d video clips sequentially "
         "(model: %s, each clip ~30–90s: upload → fal.ai queue → render → download)...",
         project_id, total, settings.fal_video_model)

    # Track which persons have appeared so far (for transition detection)
    seen_persons: set[str] = set()

    for i, (seg, clip) in enumerate(zip(segments, clips, strict=True)):
        await db.refresh(project)
        if project.status != ProjectStatus.GENERATING:
            _log("Pipeline [%s]: aborted (status=%s)", project_id, project.status.value)
            return

        seq = seg.sequence_number
        clip.status = ClipStatus.GENERATING
        clip.input_image_path = current_image
        await db.commit()

        clip_path = os.path.join(clips_dir, f"clip_{seq:03d}.mp4")
        frame_path = os.path.join(images_dir, f"last_frame_{seq:03d}.jpg")
        clip_start = time.monotonic()
        elapsed_total = time.monotonic() - pipeline_start

        seg_persons = set(p.lower() for p in (getattr(seg, "persons", None) or []))
        new_persons = seg_persons - seen_persons
        _log("Pipeline [%s]: clip %d/%d — persons in segment: %s, new: %s",
             project_id, i + 1, total, sorted(seg_persons), sorted(new_persons))

        # If this segment introduces characters not seen before,
        # generate a transition image so the video model gets a frame
        # that already contains the correct person appearance.
        input_image = current_image
        if new_persons and person_photo_map and i > 0:
            # Pass ALL characters in the segment (not just new ones) so the
            # image model can render every person accurately.
            all_seg_ref_photos = _get_segment_ref_photos(sorted(seg_persons), person_photo_map)
            if all_seg_ref_photos:
                transition_path = os.path.join(images_dir, f"transition_{seq:03d}.jpg")
                _log("Pipeline [%s]: clip %d/%d — generating transition image "
                     "for new character(s): %s (providing %d total ref photos)",
                     project_id, i + 1, total, sorted(new_persons),
                     len(all_seg_ref_photos))
                try:
                    input_image = await generate_transition_image(
                        prompt=seg.description,
                        output_path=transition_path,
                        style=project.video_style.value,
                        reference_image_paths=all_seg_ref_photos,
                        previous_frame_path=current_image,
                    )
                    _log("Pipeline [%s]: clip %d/%d — transition image ready",
                         project_id, i + 1, total)
                except Exception as exc:
                    logger.warning(
                        "Pipeline [%s]: transition image failed for clip %d, "
                        "falling back to last frame: %s",
                        project_id, seq, exc,
                    )
                    input_image = current_image

        seen_persons.update(seg_persons)

        _log(
            "Pipeline [%s]: ═══ Generating clip %d/%d ═══\n"
            "  attached image: %s\n"
            "  prompt: %s\n"
            "  style: %s\n"
            "  output: %s\n"
            "  pipeline elapsed: %.0fs",
            project_id, i + 1, total,
            input_image,
            seg.description,
            project.video_style.value,
            clip_path,
            elapsed_total,
        )

        # retry loop (FR-024)
        last_err: Exception | None = None
        for attempt in range(1 + MAX_RETRIES):
            try:
                video_path = await generate_video_clip(
                    image_path=input_image, prompt=seg.description,
                    output_path=clip_path, style=project.video_style.value,
                )
                last_err = None
                break
            except Exception as exc:
                last_err = exc
                clip.retry_count = attempt + 1
                logger.warning("Pipeline [%s]: clip %d attempt %d failed: %s",
                               project_id, seq, attempt + 1, exc)
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2)

        if last_err is not None:
            await _fail(project, db, clip, str(last_err))
            return

        # extract last frame for chaining
        try:
            current_image = await extract_last_frame(video_path, frame_path)
        except Exception as exc:
            await _fail(project, db, clip, f"Frame extraction failed: {exc}")
            return

        clip.status = ClipStatus.COMPLETED
        clip.video_file_path = video_path
        clip.last_frame_path = current_image
        clip.duration = CLIP_DURATION
        clip.generation_cost = CLIP_COST
        await db.commit()
        clip_elapsed = time.monotonic() - clip_start
        _log("Pipeline [%s]: clip %d/%d done (%.1fs) — %d remaining",
             project_id, i + 1, total, clip_elapsed, total - i - 1)

    # ── step 3: concatenate ────────────────────────────────────────
    _log("Pipeline [%s]: STEP 3/3 — concatenating %d clips into final video (ffmpeg)...",
         project_id, total)
    project.status = ProjectStatus.CONCATENATING
    await db.commit()

    try:
        final_path = await _concatenate_clips(clips_dir, output_dir, total)
    except Exception:
        logger.exception("Pipeline [%s]: concatenation failed", project_id)
        project.status = ProjectStatus.FAILED
        await db.commit()
        return

    # ── finalise ───────────────────────────────────────────────────
    total_cost = total * CLIP_COST + IMAGE_COST
    db.add(FinalVideo(
        project_id=project.id, file_path=final_path,
        total_duration=total * CLIP_DURATION,
        total_cost=total_cost,
        file_size=os.path.getsize(final_path) if os.path.exists(final_path) else 0,
    ))
    project.status = ProjectStatus.COMPLETED
    project.actual_cost = total_cost
    await db.commit()
    total_elapsed = time.monotonic() - pipeline_start
    _log("Pipeline [%s]: COMPLETED in %.0fs (%.1f min) — %s",
         project_id, total_elapsed, total_elapsed / 60, final_path)
