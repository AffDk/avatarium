"""Shared utilities for generation services."""

import os
import shutil
import tempfile
from pathlib import Path

import httpx

# Longest side in pixels for images uploaded to fal.ai.
# Keeps file size under ~200 KB and avoids 408 timeouts from OneDrive-backed
# paths where large reads cause fal.ai's PUT endpoint to time out.
_UPLOAD_MAX_PX = 1024


def prepare_image_for_upload(src_path: str) -> tuple[str, bool]:
    """Return (path_to_upload, is_temp) ready for fal.ai upload.

    Resizes the image so its longest side is <= _UPLOAD_MAX_PX and re-encodes
    as JPEG quality 85 into a system temp file.  Returns is_temp=True to signal
    the caller must delete the file after uploading.

    Falls back to (src_path, False) if Pillow is unavailable or the image
    cannot be opened.
    """
    try:
        from PIL import Image  # type: ignore[import]

        with Image.open(src_path) as img:
            w, h = img.size
            max_dim = max(w, h)
            img = img.convert("RGB")  # normalise (removes alpha, EXIF modes)
            if max_dim > _UPLOAD_MAX_PX:
                scale = _UPLOAD_MAX_PX / max_dim
                img = img.resize(
                    (int(w * scale), int(h * scale)), Image.LANCZOS
                )
            fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            img.save(tmp_path, "JPEG", quality=85, optimize=True)
            return tmp_path, True
    except Exception:
        # If anything goes wrong, use the original file unchanged
        return src_path, False


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
