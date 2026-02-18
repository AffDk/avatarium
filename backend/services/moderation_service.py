"""Moderation service — Gemini for content moderation + scenario splitting.

Uses a single combined prompt per research.md Decision 4:
one API call for both moderation and splitting.
Model is configurable via GEMINI_MODEL env var (default: gemini-2.5-flash).
"""

import json
import re
from typing import Any

import google.generativeai as genai

from backend.config import settings

# Configure Gemini on module load
genai.configure(api_key=settings.gemini_api_key)

MODERATION_SPLIT_PROMPT = """You are a content moderation and scenario splitting assistant for an AI video generation platform.

TASK: Analyze the following scenario for content safety AND split it into video segments.

CONTENT POLICY (reject if ANY apply):
- Explicit violence, gore, or torture
- Sexual or pornographic content
- Hate speech, discrimination, or slurs
- Content promoting illegal activities
- Content targeting or exploiting minors
- Self-harm or suicide promotion

SPLITTING RULES:
- Each segment should be approximately 5 seconds of video
- Maximum 15 segments total
- Each segment must be a complete, coherent scene description
- Maintain narrative flow between segments
- Include visual details suitable for image-to-video generation

SCENARIO:
{scenario_text}
{characters_section}
RESPOND WITH VALID JSON ONLY (no extra text):
{{
    "approved": true/false,
    "rejection_reason": null or "reason string",
    "characters": {{}},
    "segments": [
        {{"sequence_number": 1, "description": "Scene description...", "persons": []}},
        ...
    ]
}}

If rejected, segments should be an empty array and characters should be an empty object.
If approved, provide 1-15 segments covering the full scenario.
"""

# Appended to the prompt when person_names is provided and non-empty.
_CHARACTERS_SECTION = """
CHARACTERS (known persons from uploaded photos):
{person_names_csv}

IMPORTANT RULES FOR CHARACTERS:
- Reference each character by their given name in every segment where they appear.
- Invent a short, distinguishing visual description (2-3 traits: clothing, hair, build) for each character.
- Use EXACTLY the same visual description every time a character appears — do NOT paraphrase or add traits.
- Introduce each character's visual traits the first time they appear.
- Describe spatial relationships between characters (e.g., "Alice stands facing Bob") — do NOT use frame positions like "left of frame".
- The "characters" field in the JSON output MUST map each character name to their visual description.
- Each segment's "persons" array MUST list only the character names who appear in that segment (lowercase).
- Only use character names from the list above — do NOT invent new character names.

EXAMPLE OUTPUT (with characters):
{{
    "approved": true,
    "rejection_reason": null,
    "characters": {{
        "alice": "tall woman with curly red hair and a green dress",
        "bob": "stocky man with round glasses and a blue denim jacket"
    }},
    "segments": [
        {{"sequence_number": 1, "description": "Alice, a tall woman with curly red hair and a green dress, walks into the park.", "persons": ["alice"]}},
        {{"sequence_number": 2, "description": "Alice, the tall redhead in the green dress, waves to Bob, a stocky man with round glasses and a blue denim jacket, who approaches from across the path.", "persons": ["alice", "bob"]}}
    ]
}}
"""


async def _call_gemini(prompt: str) -> str:
    """Call Gemini and return the text response.

    This function is separated for easy mocking in tests.
    Uses response_mime_type="application/json" for reliable JSON output (Decision 2).
    """
    model = genai.GenerativeModel(settings.gemini_model)
    response = await model.generate_content_async(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
        ),
    )
    return response.text


def parse_gemini_response(
    raw_text: str,
    person_names: list[str] | None = None,
) -> dict[str, Any]:
    """Parse Gemini's JSON response, handling markdown code fences.

    Args:
        raw_text: Raw response from Gemini (may be wrapped in ```json ... ```)
        person_names: Known person names for filtering/validation. None = no persons.

    Returns:
        Parsed dict with keys: approved, rejection_reason, characters, segments

    Raises:
        ValueError: If the response cannot be parsed as JSON.
    """
    # Strip markdown code fences if present
    cleaned = raw_text.strip()
    json_match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if json_match:
        cleaned = json_match.group(1)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse Gemini response as JSON: {e}") from e

    # Validate required keys
    if "approved" not in result:
        raise ValueError("Gemini response missing 'approved' field")
    if "segments" not in result:
        raise ValueError("Gemini response missing 'segments' field")

    # Enforce max 15 segments
    if len(result.get("segments", [])) > 15:
        result["segments"] = result["segments"][:15]

    # ── Characters manifest validation (FR-014, FR-012) ─────────────────
    result.setdefault("characters", {})
    if person_names:
        characters = result["characters"]
        if not isinstance(characters, dict):
            raise ValueError(
                "Gemini response 'characters' must be a dict, "
                f"got {type(characters).__name__}"
            )
        for key, val in characters.items():
            if not isinstance(key, str) or not isinstance(val, str):
                raise ValueError(
                    "Gemini response 'characters' must have string keys and "
                    f"string values, got key={type(key).__name__}, val={type(val).__name__}"
                )

    # ── Per-segment persons validation (FR-008, FR-010, FR-005, FR-007) ─
    known_names = {n.lower() for n in person_names} if person_names else set()
    for seg in result.get("segments", []):
        seg.setdefault("persons", [])
        persons = seg["persons"]

        # FR-008: persons must be a list of strings
        if not isinstance(persons, list):
            raise ValueError(
                f"Segment {seg.get('sequence_number', '?')} 'persons' must be "
                f"a list, got {type(persons).__name__}"
            )
        for entry in persons:
            if not isinstance(entry, str):
                raise ValueError(
                    f"Segment {seg.get('sequence_number', '?')} 'persons' "
                    f"entries must be strings, got {type(entry).__name__}"
                )

        # FR-010: normalize to lowercase
        persons = [p.lower() for p in persons]

        # FR-005: filter against known person names (remove unknown)
        if known_names:
            persons = [p for p in persons if p in known_names]

        seg["persons"] = persons

    return result


async def moderate_and_split(
    scenario_text: str,
    person_names: list[str] | None = None,
) -> dict[str, Any]:
    """Moderate scenario content and split into segments using Gemini.

    Args:
        scenario_text: The raw scenario text to moderate and split.
        person_names: Known person names from uploaded photos. None = no persons.

    Returns:
        Dict with keys: approved (bool), rejection_reason (str|None),
        characters (dict), segments (list of {sequence_number, description, persons}).

    Raises:
        RuntimeError: If Gemini API call fails.
        ValueError: If response cannot be parsed.
    """
    # Build the characters section only when person_names is non-empty
    if person_names:
        characters_section = _CHARACTERS_SECTION.format(
            person_names_csv=", ".join(person_names),
        )
    else:
        characters_section = ""

    prompt = MODERATION_SPLIT_PROMPT.format(
        scenario_text=scenario_text,
        characters_section=characters_section,
    )
    raw_response = await _call_gemini(prompt)
    return parse_gemini_response(raw_response, person_names=person_names)
