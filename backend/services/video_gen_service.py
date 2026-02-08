"""Video generation service using fal.ai LTX Video 13B Distilled.

Uses fal_client.subscribe("fal-ai/ltx-video-13b-distilled/image-to-video") per research.md.
Includes last-frame extraction via ffmpeg subprocess.

Resolution: 480p (854×480) per FR-029 — lowest cost while maintaining acceptable quality.
Audio: Disabled by default per FR-022 — minimizes per-clip cost.
"""

import os
import subprocess
from pathlib import Path

import httpx

try:
    import fal_client
except ImportError:
    fal_client = None  # type: ignore[assignment]

# FR-029: Default to 480p resolution for minimum cost
DEFAULT_VIDEO_WIDTH = 854
DEFAULT_VIDEO_HEIGHT = 480


async def download_file(url: str, dest_path: str) -> str:
    """Download a file from URL to local path."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        Path(dest_path).write_bytes(resp.content)
    return dest_path


async def generate_video_clip(
    image_path: str,
    prompt: str,
    output_path: str,
) -> str:
    """Generate a ~5-second video clip from an input image using fal.ai LTX Video.

    Args:
        image_path: Path to the input image (first frame or last frame of previous clip).
        prompt: Scene description for this segment.
        output_path: Where to save the generated video clip.

    Returns:
        Path to the saved video clip.
    """
    # Read image and upload via fal
    result = await fal_client.subscribe(
        "fal-ai/ltx-video-13b-distilled/image-to-video",
        arguments={
            "prompt": prompt,
            "image_url": image_path,  # fal_client handles local file upload
            "num_frames": 121,  # ~5 seconds at 24fps
            "fps": 24,
            "width": DEFAULT_VIDEO_WIDTH,   # FR-029: 480p for minimum cost
            "height": DEFAULT_VIDEO_HEIGHT,  # FR-029: 480p for minimum cost
            "audio": False,  # FR-022: disable audio to minimize per-clip cost
        },
    )

    video_url = result["video"]["url"]
    return await download_file(video_url, output_path)


async def extract_last_frame(
    video_path: str,
    output_path: str,
) -> str:
    """Extract the last frame from a video clip using ffmpeg.

    Uses: ffmpeg -sseof -0.1 -i clip.mp4 -vframes 1 -y last_frame.jpg

    Args:
        video_path: Path to the video clip.
        output_path: Where to save the extracted frame.

    Returns:
        Path to the extracted frame image.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "ffmpeg",
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
