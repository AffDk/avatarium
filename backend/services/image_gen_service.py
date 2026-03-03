"""Image generation service using fal.ai text-to-image model.

Uses fal_client.submit_async() with manual polling (via fal_polling helper)
to avoid the default 100ms polling interval that floods logs.
"""

import logging
import os
from pathlib import Path

import httpx

from backend.config import settings
from backend.services.fal_polling import submit_and_poll

logger = logging.getLogger(__name__)

# Timeout (seconds) for fal.ai image generation. Covers queue wait + processing.
IMAGE_GEN_TIMEOUT = 300  # 5 minutes


async def download_file(url: str, dest_path: str) -> str:
    """Download a file from URL to local path."""
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        Path(dest_path).write_bytes(resp.content)
    return dest_path


async def generate_initial_image(
    prompt: str,
    output_dir: str,
    style: str = "animation",
    filename: str = "initial_image.jpg",
) -> str:
    """Generate the initial reference image using fal.ai Qwen Image.

    Args:
        prompt: Scene description for image generation.
        output_dir: Directory to save the generated image.
        style: Video style directive — "animation" or "movie_like" (FR-010).
        filename: Output filename.

    Returns:
        Path to the saved image file.

    Raises:
        RuntimeError: If the fal.ai request times out or fails.
    """
    # FR-010: Include style directive in the prompt
    style_directive = (
        "cartoon, stylized animation style"
        if style == "animation"
        else "realistic, cinematic movie style"
    )
    full_prompt = f"{prompt}, {style_directive}"
    logger.debug("Image prompt: %.200s", full_prompt)

    result = await submit_and_poll(
        settings.fal_image_model,
        arguments={"prompt": full_prompt, "image_size": "landscape_16_9"},
        timeout=IMAGE_GEN_TIMEOUT,
        label="image",
    )

    image_url = result["images"][0]["url"]
    logger.info("Image ready, downloading from %s", image_url)
    output_path = os.path.join(output_dir, filename)
    return await download_file(image_url, output_path)
