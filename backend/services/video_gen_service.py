"""Video generation service — fal.ai image-to-video + ffmpeg frame extraction.

Supports two model families, detected from settings.fal_video_model:
  • "elements" models (e.g. fal-ai/kling-video/v1.6/standard/elements):
      Accept multiple input images via input_image_urls.  First image is the
      scene/continuity frame; subsequent images are per-segment person references
      (up to 3 extras = 4 total).  Outputs 16:9 video at the requested duration.
  • LTX-style models (e.g. fal-ai/ltx-video-13b-distilled/image-to-video):
      Accept a single image_url.  Resolution and frame-count are specified
      explicitly.  Kept for backward compatibility / cheaper fallback.
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path

from backend.config import settings
from backend.services._utils import download_file, ffmpeg_exe, prepare_image_for_upload
from backend.services.fal_polling import submit_and_poll

try:
    import fal_client
except ImportError:
    fal_client = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

VIDEO_GEN_TIMEOUT = 600  # 10 min
# LTX Video native resolutions — used only when fal_video_model is LTX-style
DEFAULT_VIDEO_WIDTH = 768
DEFAULT_VIDEO_HEIGHT = 512

# Max person reference photos appended after the scene frame for elements models
_MAX_PERSON_REFS = 3


def _style_directive(style: str) -> str:
    if style == "animation":
        return "cartoon animation style"
    return "cinematic movie style, photorealistic"


_RESOLUTION_MAP: dict[str, tuple[int, int]] = {
    "480p": (768, 512),
    "720p": (1280, 720),
}


async def generate_video_clip(
    image_path: str,
    prompt: str,
    output_path: str,
    style: str = "animation",
    resolution: str = "480p",
    reference_image_paths: list[str] | None = None,
) -> str:
    """Generate a ~5-second video clip via fal.ai.

    Behaviour depends on the configured model:
    • Elements models — *image_path* is passed as the first entry of
      ``input_image_urls`` (scene/continuity frame); any *reference_image_paths*
      are appended after it (up to _MAX_PERSON_REFS extras) so the model can
      anchor the appearance of every character in the segment.
    • LTX-style models — *image_path* is passed as ``image_url``; resolution
      and frame-count are forwarded explicitly; *reference_image_paths* is
      ignored (not supported by LTX).

    Returns the local path of the saved clip.
    """
    style_dir = _style_directive(style)
    is_elements = "elements" in settings.fal_video_model

    if is_elements:
        styled_prompt = (
            f"{style_dir}. "
            "The first reference image shows the current scene — preserve its "
            "environment, background, lighting and spatial layout throughout the "
            "entire video. "
            "The additional reference images show the exact people who appear in "
            "this scene — reproduce each person's face, skin tone, hair, and "
            "clothing with complete fidelity; do NOT alter or confuse any "
            "character's appearance. "
            f"{prompt}"
        )

        images_to_upload = [image_path]
        if reference_image_paths:
            images_to_upload += reference_image_paths[:_MAX_PERSON_REFS]

        logger.info(
            "[VideoGen] ─── fal.ai elements multi-image-to-video ───\n"
            "  model: %s\n"
            "  scene frame: %s\n"
            "  person refs: %s\n"
            "  total images: %d\n"
            "  prompt: %s\n"
            "  output: %s",
            settings.fal_video_model,
            image_path,
            [os.path.basename(p) for p in (reference_image_paths or [])[:_MAX_PERSON_REFS]],
            len(images_to_upload),
            styled_prompt,
            output_path,
        )

        logger.info("[VideoGen] Uploading %d image(s) to fal.ai storage...",
                    len(images_to_upload))
        image_urls: list[str] = []
        for img_path in images_to_upload:
            compressed_path, is_temp = prepare_image_for_upload(img_path)
            try:
                url = await fal_client.upload_file_async(compressed_path)
                image_urls.append(url)
            finally:
                if is_temp:
                    try:
                        os.unlink(compressed_path)
                    except OSError:
                        pass
        logger.info("[VideoGen] All images uploaded — submitting to fal.ai queue...")

        result = await submit_and_poll(
            settings.fal_video_model,
            arguments={
                "prompt": styled_prompt,
                "input_image_urls": image_urls,
                "duration": "5",
                "aspect_ratio": "16:9",
                "negative_prompt": "blur, distort, and low quality",
            },
            timeout=VIDEO_GEN_TIMEOUT,
            label="video",
        )
    else:
        # LTX-style single-image model (backward compatibility)
        width, height = _RESOLUTION_MAP.get(resolution, (DEFAULT_VIDEO_WIDTH, DEFAULT_VIDEO_HEIGHT))
        styled_prompt = (
            f"{style_dir}. "
            "IMPORTANT: The input image is the GROUND TRUTH for character "
            "appearance — it was generated from real reference photos. "
            "Preserve every character's face, identity, skin tone, hair, "
            "clothing, and body proportions EXACTLY as shown in the input "
            "image throughout the entire video. Do NOT alter, distort, or "
            "reimagine any person's appearance during the animation. "
            f"{prompt}"
        )

        logger.info(
            "[VideoGen] ─── fal.ai image-to-video ───\n"
            "  model: %s\n"
            "  input image: %s\n"
            "  prompt: %s\n"
            "  resolution: %dx%d (%s)\n"
            "  frames: 121 @ 24fps (~5s)\n"
            "  output: %s",
            settings.fal_video_model,
            image_path,
            styled_prompt,
            width,
            height,
            resolution,
            output_path,
        )
        logger.info("[VideoGen] Uploading input image to fal.ai storage...")
        image_url = await fal_client.upload_file_async(image_path)
        logger.info("[VideoGen] Input image uploaded — submitting to fal.ai queue...")

        result = await submit_and_poll(
            settings.fal_video_model,
            arguments={
                "prompt": styled_prompt,
                "image_url": image_url,
                "num_frames": 121,
                "fps": 24,
                "width": width,
                "height": height,
                "audio": False,
            },
            timeout=VIDEO_GEN_TIMEOUT,
            label="video",
        )

    video_url = result["video"]["url"]
    logger.info("[VideoGen] Video clip ready: %s", video_url)
    return await download_file(video_url, output_path)


async def extract_last_frame(video_path: str, output_path: str) -> str:
    """Extract the last frame from *video_path* using ffmpeg. Returns *output_path*."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(
        subprocess.run,
        [
            ffmpeg_exe(),
            "-sseof", "-0.1",
            "-i", video_path,
            "-vframes", "1",
            "-y",
            output_path,
        ],
        check=True,
        capture_output=True,
    )
    return output_path
