"""Upload service — filename parsing, validation, person grouping, and person-reference validation."""

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 10_485_760  # 10 MB

# Pattern: <personName>_<sequenceNumber>.<extension>
FILENAME_PATTERN = re.compile(
    r"^(?P<person>[a-zA-Z0-9]+)_(?P<seq>\d+)\.(?P<ext>[a-zA-Z0-9]+)$"
)


def parse_filename(filename: str) -> tuple[str, int]:
    """Parse a photo filename into (person_name, sequence_number).

    Expected format: <personName>_<sequenceNumber>.<extension>
    Person name is normalized to lowercase.

    Raises:
        ValueError: If filename doesn't match the expected pattern.
    """
    match = FILENAME_PATTERN.match(filename)
    if match is None:
        raise ValueError(
            f"Invalid filename '{filename}'. "
            "Expected format: <personName>_<sequenceNumber>.<extension> "
            "(e.g., alice_1.jpg)"
        )

    person = match.group("person").lower()
    seq = int(match.group("seq"))
    ext = match.group("ext").lower()

    if not person:
        raise ValueError(f"Invalid filename '{filename}': empty person name.")

    if seq < 1:
        raise ValueError(
            f"Invalid filename '{filename}': sequence number must be ≥ 1, got {seq}."
        )

    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Invalid filename '{filename}': unsupported extension '.{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    return person, seq


def validate_file(file: Any) -> None:
    """Validate an uploaded file's MIME type and size.

    Args:
        file: An UploadFile-like object with .content_type and .size attributes.

    Raises:
        ValueError: If file exceeds 10MB or has unsupported MIME type.
    """
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise ValueError(
            f"Unsupported MIME type '{file.content_type}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
        )

    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise ValueError(
            f"File size ({file.size} bytes) exceeds 10 MB limit."
        )


def group_files_by_person(
    parsed_files: list[tuple[str, str, int]],
) -> dict[str, list[tuple[str, str, int]]]:
    """Group parsed file entries by person name.

    Args:
        parsed_files: List of (original_filename, person_name, sequence_number) tuples.

    Returns:
        Dict mapping person_name to list of (filename, person, seq) tuples.
    """
    groups: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    for entry in parsed_files:
        _, person, _ = entry
        groups[person].append(entry)
    return dict(groups)


def validate_person_references(
    scenario_text: str,
    person_names: list[str],
) -> list[str]:
    """Validate that uploaded person names are referenced in the scenario text (FR-008).

    Performs case-insensitive substring search for each person name in the scenario.
    Returns warnings for person names NOT found in the scenario text.

    Args:
        scenario_text: The raw scenario text.
        person_names: List of person names (lowercase) from uploaded photos.

    Returns:
        List of warning strings for unreferenced persons.
    """
    if not person_names:
        return []

    scenario_lower = scenario_text.lower()
    warnings: list[str] = []

    for name in person_names:
        if name.lower() not in scenario_lower:
            warnings.append(
                f"Person '{name}' has uploaded photos but is not mentioned in the scenario."
            )

    return warnings


async def save_photo_file(
    file: Any,
    user_id: str,
    project_id: str,
    filename: str,
    upload_dir: str = "uploads",
) -> str:
    """Save an uploaded photo to the user-scoped directory.

    Directory structure: uploads/{user_id}/{project_id}/{filename}

    Returns:
        The relative file path where the photo was saved.
    """
    dest_dir = Path(upload_dir) / user_id / project_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_path = dest_dir / filename
    content = await file.read()
    dest_path.write_bytes(content)

    return str(dest_path)
