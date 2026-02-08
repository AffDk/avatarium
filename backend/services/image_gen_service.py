"""Image generation service using fal.ai Qwen Image model.

Uses fal_client.subscribe("fal-ai/qwen-image") per research.md.
"""

import os
from pathlib import Path

import httpx

try:
    import fal_client
except ImportError:
    fal_client = None  # type: ignore[assignment]


async def download_file(url: str, dest_path: str) -> str:
    """Download a file from URL to local path."""
    async with httpx.AsyncClient() as client:
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
    """
    # FR-010: Include style directive in the prompt
    style_directive = (
        "cartoon, stylized animation style"
        if style == "animation"
        else "realistic, cinematic movie style"
    )
    full_prompt = f"{prompt}, {style_directive}"

    result = await fal_client.subscribe(
        "fal-ai/qwen-image",
        arguments={
            "prompt": full_prompt,
            "image_size": "landscape_16_9",
        },
    )

    image_url = result["images"][0]["url"]
    output_path = os.path.join(output_dir, filename)
    return await download_file(image_url, output_path)
