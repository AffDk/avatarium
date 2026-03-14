"""Shared utilities for generation services."""

import shutil
from pathlib import Path

import httpx


async def download_file(url: str, dest_path: str) -> str:
    """Download a file from *url* and save it to *dest_path*."""
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        Path(dest_path).write_bytes(resp.content)
    return dest_path


def ffmpeg_exe() -> str:
    """Resolve the ffmpeg binary: system PATH → imageio_ffmpeg bundle → bare name."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"
