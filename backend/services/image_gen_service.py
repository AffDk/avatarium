"""Image generation service — fal.ai text-to-image / image-to-image.

When reference photos are provided (uploaded person photos), they are
uploaded to fal.ai and passed as image references so the generated
image incorporates the actual people from the project.
"""

import logging
import os

from backend.config import settings
from backend.services._utils import download_file, prepare_image_for_upload
from backend.services.fal_polling import submit_and_poll

try:
    import fal_client
except ImportError:
    fal_client = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

IMAGE_GEN_TIMEOUT = 300  # 5 min

_MAX_REF_PHOTOS = 3


async def _upload_reference_photos(photo_paths: list[str]) -> list[str]:
    """Upload up to *_MAX_REF_PHOTOS* local photos to fal.ai storage.

    Each photo is first compressed to ≤1024 px longest side via
    prepare_image_for_upload() so large files / OneDrive-backed paths
    never trigger fal.ai's 408 upload timeout.
    """
    urls: list[str] = []
    for path in photo_paths[:_MAX_REF_PHOTOS]:
        compressed_path, is_temp = prepare_image_for_upload(path)
        try:
            url = await fal_client.upload_file_async(compressed_path)
            urls.append(url)
            logger.info("Uploaded reference photo %s → %s", path, url)
        except Exception as exc:
            logger.warning("Failed to upload reference photo %s: %s", path, exc)
        finally:
            if is_temp:
                try:
                    os.unlink(compressed_path)
                except OSError:
                    pass
    return urls


def _style_directive(style: str) -> str:
    if style == "animation":
        return (
            "stylized cartoon animation style, consistent cel-shaded look, "
            "vibrant colors, smooth animation"
        )
    return (
        "photorealistic cinematic movie style, natural lighting, film grain, "
        "shallow depth of field, live-action cinematography"
    )


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
    style_dir = _style_directive(style)

    if reference_image_paths:
        # When reference photos are provided, instruct the model explicitly
        # to generate an image featuring the people from the reference photos.
        full_prompt = (
            f"Generate a single image in {style_dir}. "
            "CRITICAL INSTRUCTION: The attached reference photo(s) are the "
            "SOLE AUTHORITY for character appearance. You MUST use the "
            "reference photo(s) as the definitive source — directly copy the "
            "face, identity, and likeness from the reference photo(s) into "
            "the generated image. Do NOT invent, alter, or reimagine any "
            "aspect of the person's appearance. The generated characters "
            "must be visually INDISTINGUISHABLE from the reference photos. "
            "Treat the reference photo(s) as ground truth — every facial "
            "feature, skin tone, hair, and body proportion must be "
            "faithfully reproduced. "
            f"Scene: {prompt}"
        )
    else:
        full_prompt = f"{prompt}, {style_dir}"

    arguments: dict = {"additional_prompt": full_prompt, "image_size": "landscape_16_9"}

    if reference_image_paths:
        logger.info("Uploading %d reference photo(s) to fal.ai storage...",
                    len(reference_image_paths[:_MAX_REF_PHOTOS]))
        ref_urls = await _upload_reference_photos(reference_image_paths)
        if ref_urls:
            arguments["image_urls"] = ref_urls
            logger.info("Reference photos uploaded — submitting image generation request")

    logger.info(
        "[ImageGen] ─── fal.ai text-to-image (initial) ───\n"
        "  model: %s\n"
        "  prompt: %s\n"
        "  ref photos: %s\n"
        "  image_size: landscape_16_9",
        settings.fal_image_model,
        full_prompt,
        [os.path.basename(p) for p in (reference_image_paths or [])],
    )

    result = await submit_and_poll(
        settings.fal_image_model,
        arguments=arguments,
        timeout=IMAGE_GEN_TIMEOUT,
        label="image",
    )

    image_url = result["images"][0]["url"]
    logger.info("Image ready: %s", image_url)
    return await download_file(image_url, os.path.join(output_dir, filename))


async def generate_transition_image(
    prompt: str,
    output_path: str,
    style: str = "animation",
    reference_image_paths: list[str] | None = None,
    previous_frame_path: str | None = None,
) -> str:
    """Generate a transition image for a segment that introduces new characters.

    When a new character appears who wasn't in the previous frame, we can't
    rely on last-frame chaining alone — the video model would invent their
    appearance.  Instead we ask the image model to generate a new scene
    frame that incorporates the new character's reference photo(s).

    If *previous_frame_path* is provided it is uploaded as context so the
    image model can maintain scene continuity (same environment, lighting,
    existing characters).

    Returns the local path of the saved image.
    """
    style_dir = _style_directive(style)

    if reference_image_paths:
        full_prompt = (
            f"Generate a single image in {style_dir}. "
            "CRITICAL INSTRUCTION: The attached reference photo(s) are the "
            "SOLE AUTHORITY for character appearance. You MUST use the "
            "reference photo(s) as the definitive source — directly copy the "
            "face, identity, and likeness from the reference photo(s) into "
            "the generated image. Do NOT invent, alter, or reimagine any "
            "aspect of the person's appearance. The generated characters "
            "must be visually INDISTINGUISHABLE from the reference photos. "
            "Treat the reference photo(s) as ground truth — every facial "
            "feature, skin tone, hair, and body proportion must be "
            "faithfully reproduced. "
        )
        if previous_frame_path:
            full_prompt += (
                "Also attached is an image of the CURRENT SCENE — maintain "
                "the same environment, lighting, and camera angle while "
                "incorporating the referenced people. "
            )
        full_prompt += f"Scene: {prompt}"
    else:
        full_prompt = f"{prompt}, {style_dir}"

    arguments: dict = {"additional_prompt": full_prompt, "image_size": "landscape_16_9"}

    # Build the list of images to upload.
    # Person reference photos go FIRST so the model anchors on character
    # appearance.  The previous frame is appended last as supplementary
    # scene-continuity context.
    ref_urls: list[str] = []
    if reference_image_paths:
        ref_urls = await _upload_reference_photos(reference_image_paths)

    prev_frame_url: str | None = None
    if previous_frame_path:
        compressed_path, is_temp = prepare_image_for_upload(previous_frame_path)
        try:
            prev_frame_url = await fal_client.upload_file_async(compressed_path)
            logger.info("Uploaded previous frame for transition: %s", prev_frame_url)
        except Exception as exc:
            logger.warning("Failed to upload previous frame: %s", exc)
        finally:
            if is_temp:
                try:
                    os.unlink(compressed_path)
                except OSError:
                    pass

    all_urls = ref_urls + ([prev_frame_url] if prev_frame_url else [])

    if all_urls:
        arguments["image_urls"] = all_urls

    logger.info(
        "[ImageGen] ─── fal.ai text-to-image (transition) ───\n"
        "  model: %s\n"
        "  prompt: %s\n"
        "  ref photos: %s\n"
        "  previous frame: %s\n"
        "  total image URLs: %d",
        settings.fal_image_model,
        full_prompt,
        [os.path.basename(p) for p in (reference_image_paths or [])],
        previous_frame_path,
        len(all_urls),
    )

    result = await submit_and_poll(
        settings.fal_image_model,
        arguments=arguments,
        timeout=IMAGE_GEN_TIMEOUT,
        label="image",
    )

    image_url = result["images"][0]["url"]
    logger.info("Transition image ready: %s", image_url)
    return await download_file(image_url, output_path)
