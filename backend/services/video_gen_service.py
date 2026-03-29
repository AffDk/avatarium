"""Video generation service — fal.ai LTX Video image-to-video + ffmpeg frame extraction.

Resolution: 768x512 (LTX Video native landscape). Audio disabled per FR-022.
"""

import asyncio
import logging
import subprocess
from pathlib import Path

from backend.config import settings
from backend.services._utils import download_file, ffmpeg_exe
from backend.services.fal_polling import submit_and_poll

try:
    import fal_client
except ImportError:
    fal_client = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

VIDEO_GEN_TIMEOUT = 600  # 10 min
# LTX Video native resolutions — use 768x512 for landscape
DEFAULT_VIDEO_WIDTH = 768
DEFAULT_VIDEO_HEIGHT = 512


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
) -> str:
    """Generate a ~5-second video clip from *image_path* via fal.ai LTX Video.

    The input image is used as the starting frame.  Character continuity
    relies on last-frame chaining and descriptive text prompts — no
    composite images are used.

    Returns the local path of the saved clip.
    """
    width, height = _RESOLUTION_MAP.get(resolution, (DEFAULT_VIDEO_WIDTH, DEFAULT_VIDEO_HEIGHT))
    style_dir = _style_directive(style)
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
