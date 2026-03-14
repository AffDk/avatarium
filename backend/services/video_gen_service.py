"""Video generation service — fal.ai LTX Video image-to-video + ffmpeg frame extraction.

Resolution: 480p (854x480) per FR-029. Audio disabled per FR-022.
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
DEFAULT_VIDEO_WIDTH = 854
DEFAULT_VIDEO_HEIGHT = 480


def _style_directive(style: str) -> str:
    if style == "animation":
        return "cartoon, stylized animation style"
    return "realistic, cinematic movie style"


async def generate_video_clip(
    image_path: str,
    prompt: str,
    output_path: str,
    style: str = "animation",
    has_person_refs: bool = False,
) -> str:
    """Generate a ~5-second video clip from *image_path* via fal.ai LTX Video.

    When *has_person_refs* is True, the input image is a composite containing
    the last frame at the top and person reference photos at the bottom.
    The prompt is augmented to instruct the model to use the top portion as
    the scene continuation and incorporate the referenced characters.

    Returns the local path of the saved clip.
    """
    styled_prompt = f"{prompt}, {_style_directive(style)}"
    if has_person_refs:
        styled_prompt = (
            "Continue the scene shown in the top portion of the reference image. "
            "The characters shown in the bottom strip are the people in this scene — "
            "use their appearance as reference. " + styled_prompt
        )

    logger.info("Uploading input image to fal.ai storage...")
    image_url = await fal_client.upload_file_async(image_path)
    logger.info("Input image uploaded — submitting video generation to fal.ai queue...")

    result = await submit_and_poll(
        settings.fal_video_model,
        arguments={
            "prompt": styled_prompt,
            "image_url": image_url,
            "num_frames": 121,
            "fps": 24,
            "width": DEFAULT_VIDEO_WIDTH,
            "height": DEFAULT_VIDEO_HEIGHT,
            "audio": False,
        },
        timeout=VIDEO_GEN_TIMEOUT,
        label="video",
    )

    video_url = result["video"]["url"]
    logger.info("Video clip ready: %s", video_url)
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
