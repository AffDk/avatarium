"""Composite image service — merge last frame + person reference photos into one image.

The fal.ai LTX Video image-to-video endpoint accepts only a SINGLE image_url.
To pass both visual continuity (last frame) and character reference photos to the
model, we composite them into a single image:

┌──────────────────────────────────┐
│          LAST FRAME              │  ← large, top section (continuity)
│       (from prev segment)        │
├────────┬────────┬────────────────┤
│ Person │ Person │ ...            │  ← smaller strip at bottom (references)
│  Photo │  Photo │                │
└────────┴────────┴────────────────┘

The prompt instructs the model to continue the scene from the top image while
incorporating the characters shown in the reference strip.
"""

import logging
import os

from PIL import Image

logger = logging.getLogger(__name__)

# Reference photo strip height as a fraction of the main frame height
REF_STRIP_RATIO = 0.25
# Maximum number of reference photos to include in the composite
MAX_REF_PHOTOS_IN_COMPOSITE = 3
# JPEG quality for the composite output
JPEG_QUALITY = 92


def create_composite_image(
    last_frame_path: str,
    reference_photo_paths: list[str],
    output_path: str,
) -> str:
    """Create a composite image combining the last frame with person reference photos.

    The last frame occupies the top ~80% of the image, and person photos
    are arranged in a horizontal strip at the bottom ~20%.

    Args:
        last_frame_path: Path to the last frame from the preceding segment.
        reference_photo_paths: Paths to person reference photos for this segment.
        output_path: Where to save the composite image.

    Returns:
        The output_path on success.
    """
    if not reference_photo_paths:
        # No person photos to composite — just return the last frame as-is
        return last_frame_path

    # Load the main frame
    main_frame = Image.open(last_frame_path).convert("RGB")
    main_w, main_h = main_frame.size

    # Load reference photos (skip missing/broken files)
    ref_images: list[Image.Image] = []
    for path in reference_photo_paths[:MAX_REF_PHOTOS_IN_COMPOSITE]:
        if not os.path.exists(path):
            logger.warning("Composite: reference photo missing: %s", path)
            continue
        try:
            ref_images.append(Image.open(path).convert("RGB"))
        except Exception as exc:
            logger.warning("Composite: failed to open %s: %s", path, exc)

    if not ref_images:
        return last_frame_path

    # Calculate dimensions
    ref_strip_h = int(main_h * REF_STRIP_RATIO)
    total_h = main_h + ref_strip_h

    # Create the composite canvas
    composite = Image.new("RGB", (main_w, total_h), color=(0, 0, 0))

    # Paste the main frame at the top
    composite.paste(main_frame, (0, 0))

    # Arrange reference photos in the bottom strip, evenly spaced
    n_refs = len(ref_images)
    cell_w = main_w // n_refs

    for i, ref_img in enumerate(ref_images):
        # Resize each reference photo to fit its cell, maintaining aspect ratio
        rw, rh = ref_img.size
        scale = min(cell_w / rw, ref_strip_h / rh)
        new_w = int(rw * scale)
        new_h = int(rh * scale)
        resized = ref_img.resize((new_w, new_h), Image.LANCZOS)

        # Center within the cell
        x_offset = i * cell_w + (cell_w - new_w) // 2
        y_offset = main_h + (ref_strip_h - new_h) // 2
        composite.paste(resized, (x_offset, y_offset))

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    composite.save(output_path, "JPEG", quality=JPEG_QUALITY)
    logger.info(
        "Composite image created: %s (%dx%d, %d ref photos)",
        output_path, main_w, total_h, n_refs,
    )
    return output_path
