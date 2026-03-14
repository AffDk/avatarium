"""Image generation service — fal.ai text-to-image / image-to-image.

When reference photos are provided (uploaded person photos), they are
uploaded to fal.ai and passed as image references so the generated
image incorporates the actual people from the project.
"""

import logging
import os

from backend.config import settings
from backend.services._utils import download_file
from backend.services.fal_polling import submit_and_poll

try:
    import fal_client
except ImportError:
    fal_client = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

IMAGE_GEN_TIMEOUT = 300  # 5 min

_MAX_REF_PHOTOS = 3


async def _upload_reference_photos(photo_paths: list[str]) -> list[str]:
    """Upload up to *_MAX_REF_PHOTOS* local photos to fal.ai storage."""
    urls: list[str] = []
    for path in photo_paths[:_MAX_REF_PHOTOS]:
        try:
            url = await fal_client.upload_file_async(path)
            urls.append(url)
            logger.info("Uploaded reference photo %s → %s", path, url)
        except Exception as exc:
            logger.warning("Failed to upload reference photo %s: %s", path, exc)
    return urls


def _style_directive(style: str) -> str:
    if style == "animation":
        return "cartoon, stylized animation style"
    return "realistic, cinematic movie style"


async def generate_initial_image(
    prompt: str,
    output_dir: str,
    style: str = "animation",
    filename: str = "initial_image.jpg",
    reference_image_paths: list[str] | None = None,
) -> str:
    """Generate the initial reference image via fal.ai.

    Returns the local path of the saved image.
    """
    full_prompt = f"{prompt}, {_style_directive(style)}"
    arguments: dict = {"prompt": full_prompt, "image_size": "landscape_16_9"}

    if reference_image_paths:
        logger.info("Uploading %d reference photo(s) to fal.ai storage...",
                    len(reference_image_paths[:_MAX_REF_PHOTOS]))
        ref_urls = await _upload_reference_photos(reference_image_paths)
        if ref_urls:
            arguments["image_url"] = ref_urls[0]
            if len(ref_urls) > 1:
                arguments["image_urls"] = ref_urls
            logger.info("Reference photos uploaded — submitting image generation request")

    result = await submit_and_poll(
        settings.fal_image_model,
        arguments=arguments,
        timeout=IMAGE_GEN_TIMEOUT,
        label="image",
    )

    image_url = result["images"][0]["url"]
    logger.info("Image ready: %s", image_url)
    return await download_file(image_url, os.path.join(output_dir, filename))
