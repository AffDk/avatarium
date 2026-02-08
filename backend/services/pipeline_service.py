"""Pipeline orchestration service — iterative video generation.

Orchestrates the full pipeline:
1. Generate initial image from first segment description + style
2. For each segment: generate video clip → extract last frame
3. Use last frame as input for next segment's video
4. Retry failed clips once (FR-024)
"""

import os
from pathlib import Path

from backend.services.image_gen_service import generate_initial_image
from backend.services.video_gen_service import extract_last_frame, generate_video_clip

MAX_RETRIES = 1  # FR-024: retry a failed clip once automatically


async def run_pipeline(
    segments: list[dict],
    style: str,
    output_dir: str,
    person_names: list[str],
) -> list[dict]:
    """Run the iterative video generation pipeline.

    Args:
        segments: List of segment dicts with 'sequence_number' and 'description'.
        style: Video style — "animation" or "movie_like".
        output_dir: Directory for generated files.
        person_names: List of person names from uploaded photos.

    Returns:
        List of result dicts per clip: {sequence_number, video_path, last_frame_path}.

    Raises:
        RuntimeError: If a clip fails after all retries exhausted.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    images_dir = os.path.join(output_dir, "images")
    clips_dir = os.path.join(output_dir, "clips")
    Path(images_dir).mkdir(parents=True, exist_ok=True)
    Path(clips_dir).mkdir(parents=True, exist_ok=True)

    # Step 1: Generate initial image from first segment
    first_segment = segments[0]
    person_str = ", ".join(person_names) if person_names else ""
    initial_prompt = f"{first_segment['description']}. Characters: {person_str}"

    current_image = await generate_initial_image(
        prompt=initial_prompt,
        output_dir=images_dir,
        style=style,
    )

    # Step 2: Iterate through segments — generate video → extract last frame
    results: list[dict] = []

    for segment in segments:
        seq = segment["sequence_number"]
        clip_path = os.path.join(clips_dir, f"clip_{seq}.mp4")
        frame_path = os.path.join(images_dir, f"last_frame_{seq}.jpg")

        # Generate video clip with retry logic (FR-024)
        last_error: Exception | None = None
        for attempt in range(1 + MAX_RETRIES):
            try:
                video_path = await generate_video_clip(
                    image_path=current_image,
                    prompt=segment["description"],
                    output_path=clip_path,
                )
                last_error = None
                break
            except Exception as e:
                last_error = e

        if last_error is not None:
            raise last_error

        # Extract last frame for next segment's input
        current_image = await extract_last_frame(
            video_path=video_path,
            output_path=frame_path,
        )

        results.append({
            "sequence_number": seq,
            "video_path": video_path,
            "last_frame_path": current_image,
        })

    return results
