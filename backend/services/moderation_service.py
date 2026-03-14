"""Moderation service — Gemini for content moderation + scenario splitting.

Uses a single combined prompt per research.md Decision 4:
one API call for both moderation and splitting.
Model is configurable via GEMINI_MODEL env var (default: gemini-2.5-flash).

Supports multimodal input: when reference photos are provided, they are sent
alongside the text prompt so Gemini can describe characters accurately.
"""

import json
import logging
import re
from typing import Any

import google.generativeai as genai
from PIL import Image

from backend.config import settings

# Configure Gemini on module load
genai.configure(api_key=settings.gemini_api_key)

logger = logging.getLogger(__name__)

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

MOVEMENT DIRECTION & CONTINUITY RULES:
- For each segment, explicitly state the direction of movement of every character (e.g., "walking left to right", "moving toward the camera", "turning from left to right").
- The direction of movement of a character MUST stay consistent across consecutive segments unless the scenario explicitly calls for a change.
- If a character was moving left-to-right in one segment, they must continue left-to-right in the next unless the narrative requires them to stop or turn around — and that turn must be described explicitly.
- Never abruptly reverse a character's direction between segments without narrative justification.

PHYSICAL REALISM & SPATIAL CONSISTENCY RULES:
- Characters MUST interact with solid objects realistically: they open doors before walking through them, walk around furniture, and stop at walls or barriers.
- A character MUST NOT pass through, overlap with, or phase through any solid object (walls, windows, doors, fences, tables, cars, etc.).
- If a character needs to go through a door or gate, explicitly describe them opening it, stepping through, and optionally closing it.
- If a character needs to enter or exit through a window, describe them opening the window first — or explicitly describe the window breaking if that is the narrative intent.
- Characters must walk ON surfaces (ground, floor, stairs), not float above or sink below them.
- When a character sits down, describe them lowering onto the seat; when they stand, describe them rising. Do not teleport between standing and sitting.
- Describe transitions between indoor and outdoor spaces explicitly (e.g., "pushes open the front door and steps outside onto the porch").
- If two characters interact physically (handshake, hug, passing an object), describe the reach and contact clearly so the generation model places them at a plausible distance.
- Avoid describing actions that defy gravity or basic physics unless the scenario is explicitly fantastical — and even then, describe the supernatural element clearly (e.g., "magically floats upward").

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
_CHARACTERS_SECTION_WITH_PHOTOS = """
CHARACTERS (known persons from uploaded photos — reference photos are attached below):
{person_names_csv}

CRITICAL — CHARACTER APPEARANCE RULES (you MUST follow ALL of these in EVERY segment):
- Reference photos for each character are attached to this message. Study them carefully.
- Describe each character's ACTUAL visual appearance based on the attached reference photos — do NOT invent or guess traits.
- Include accurate details: hair color, hair style, skin tone, approximate age, clothing, build, and any distinguishing features EXACTLY as seen in the photos.

*** MANDATORY PHOTO REFERENCE IN EVERY SEGMENT ***
- EVERY segment description that mentions a character MUST include the phrase "as seen in the reference photo" AND a visual description of that character.
- This is NOT optional. A segment that mentions a character by name but omits their visual description or "as seen in the reference photo" is INVALID.
- Do NOT write a segment like: "Alice walks into the park." — this is WRONG because it lacks the visual description and photo reference.
- CORRECT: "Alice, a tall woman with straight dark brown hair in a red jacket as seen in the reference photo, walks into the park."
- WRONG: "Alice walks into the park." (missing visual description and photo reference — NEVER do this)
- WRONG: "Alice, the tall brunette, walks into the park." (missing "as seen in the reference photo" — NEVER do this)
- Even if a character appeared in a previous segment, you MUST repeat their visual description with "as seen in the reference photo" in EVERY segment they appear in. The video generation model processes each segment independently and has no memory of previous segments.
- Use EXACTLY the same visual description every time a character appears — do NOT paraphrase or add traits.
- Describe spatial relationships between characters (e.g., "Alice stands facing Bob") — do NOT use frame positions like "left of frame".
- The "characters" field in the JSON output MUST map each character name to their visual description derived from the reference photos.
- Each segment's "persons" array MUST list only the character names who appear in that segment (lowercase).
- Only use character names from the list above — do NOT invent new character names.

EXAMPLE OUTPUT (with characters):
{{
    "approved": true,
    "rejection_reason": null,
    "characters": {{
        "alice": "tall woman with straight dark brown hair, light skin, wearing a red jacket as seen in the reference photo",
        "bob": "stocky man with short black hair, round glasses, wearing a blue denim jacket as seen in the reference photo"
    }},
    "segments": [
        {{"sequence_number": 1, "description": "Alice, a tall woman with straight dark brown hair in a red jacket as seen in the reference photo, walks left to right into the park.", "persons": ["alice"]}},
        {{"sequence_number": 2, "description": "Alice, a tall woman with straight dark brown hair in a red jacket as seen in the reference photo, continues walking left to right and waves to Bob, a stocky man with short black hair and round glasses in a blue denim jacket as seen in the reference photo, who approaches from the right.", "persons": ["alice", "bob"]}}
    ]
}}

NOTICE: In segment 2 above, Alice's full visual description with "as seen in the reference photo" is repeated even though she appeared in segment 1. This is REQUIRED for every segment.
"""

_CHARACTERS_SECTION_NO_PHOTOS = """
CHARACTERS (known persons from uploaded photos):
{person_names_csv}

CRITICAL — CHARACTER APPEARANCE RULES (you MUST follow ALL of these in EVERY segment):
- Reference each character by their given name in every segment where they appear.
- Provide a short, distinguishing visual description (2-3 traits: clothing, hair, build) for each character.
- Use EXACTLY the same visual description every time a character appears — do NOT paraphrase or add traits.

*** MANDATORY PHOTO REFERENCE IN EVERY SEGMENT ***
- EVERY segment description that mentions a character MUST include the phrase "as seen in the reference photo" AND a visual description of that character.
- This is NOT optional. A segment that mentions a character by name but omits their visual description or "as seen in the reference photo" is INVALID.
- Do NOT write a segment like: "Alice walks into the park." — this is WRONG because it lacks the visual description and photo reference.
- CORRECT: "Alice, a tall woman with curly red hair in a green dress as seen in the reference photo, walks into the park."
- Even if a character appeared in a previous segment, you MUST repeat their visual description with "as seen in the reference photo" in EVERY segment they appear in. The video generation model processes each segment independently and has no memory of previous segments.
- Describe spatial relationships between characters (e.g., "Alice stands facing Bob") — do NOT use frame positions like "left of frame".
- The "characters" field in the JSON output MUST map each character name to their visual description.
- Each segment's "persons" array MUST list only the character names who appear in that segment (lowercase).
- Only use character names from the list above — do NOT invent new character names.

EXAMPLE OUTPUT (with characters):
{{
    "approved": true,
    "rejection_reason": null,
    "characters": {{
        "alice": "tall woman with curly red hair and a green dress as seen in the reference photo",
        "bob": "stocky man with round glasses and a blue denim jacket as seen in the reference photo"
    }},
    "segments": [
        {{"sequence_number": 1, "description": "Alice, a tall woman with curly red hair and a green dress as seen in the reference photo, walks left to right into the park.", "persons": ["alice"]}},
        {{"sequence_number": 2, "description": "Alice, a tall woman with curly red hair in a green dress as seen in the reference photo, continues left to right and waves to Bob, a stocky man with round glasses and a blue denim jacket as seen in the reference photo, who approaches from the right.", "persons": ["alice", "bob"]}}
    ]
}}

NOTICE: In segment 2 above, Alice's full visual description with "as seen in the reference photo" is repeated even though she appeared in segment 1. This is REQUIRED for every segment.
"""


def _load_photo_images(photo_paths: dict[str, list[str]]) -> list[tuple[str, Image.Image]]:
    """Load photo files as PIL Images for multimodal Gemini input.

    Args:
        photo_paths: Mapping of person_name → list of file paths.

    Returns:
        List of (label, PIL.Image) tuples. Only the first photo per person is used.
    """
    images: list[tuple[str, Image.Image]] = []
    for person_name, paths in sorted(photo_paths.items()):
        for path in paths[:1]:  # Use first photo per person to keep request small
            try:
                img = Image.open(path)
                # Resize large images to reduce token cost
                max_dim = 1024
                if max(img.size) > max_dim:
                    ratio = max_dim / max(img.size)
                    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                    img = img.resize(new_size, Image.LANCZOS)
                images.append((person_name, img))
                logger.info("Loaded reference photo for '%s': %s", person_name, path)
            except Exception as exc:
                logger.warning("Failed to load photo for '%s' at %s: %s", person_name, path, exc)
    return images


async def _call_gemini(prompt: str, images: list[tuple[str, Image.Image]] | None = None) -> str:
    """Call Gemini and return the text response.

    This function is separated for easy mocking in tests.
    Uses response_mime_type="application/json" for reliable JSON output (Decision 2).
    Supports multimodal input when images are provided.
    """
    model = genai.GenerativeModel(settings.gemini_model)

    if images:
        # Build multimodal content: text prompt + labeled images
        content: list[Any] = [prompt]
        for person_name, img in images:
            content.append(f"\n[Reference photo for {person_name}]:")
            content.append(img)
        logger.info("Sending multimodal request to Gemini with %d reference photos", len(images))
        response = await model.generate_content_async(
            content,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
            ),
        )
    else:
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

        # Coerce entries: Gemini sometimes returns dicts like {"name": "alice"}
        # instead of plain strings. Extract the name and continue.
        coerced: list[str] = []
        for entry in persons:
            if isinstance(entry, str):
                coerced.append(entry)
            elif isinstance(entry, dict):
                # Try common key names Gemini might use
                name = entry.get("name") or entry.get("person") or entry.get("character")
                if isinstance(name, str):
                    coerced.append(name)
                else:
                    # Last resort: take the first string value from the dict
                    for v in entry.values():
                        if isinstance(v, str):
                            coerced.append(v)
                            break
            # Silently skip other non-string types
        persons = coerced

        # FR-010: normalize to lowercase
        persons = [p.lower() for p in persons]

        # FR-005: filter against known person names (remove unknown)
        if known_names:
            persons = [p for p in persons if p in known_names]

        seg["persons"] = persons

    # Post-process: enforce character visual descriptions in every segment
    _enforce_character_descriptions_in_segments(result)

    return result


def _enforce_character_descriptions_in_segments(result: dict[str, Any]) -> None:
    """Inject missing character visual descriptions into segment descriptions.

    Gemini sometimes omits the character's visual description or the
    "as seen in the reference photo" phrase from segment descriptions despite
    explicit instructions.  This function patches any segment whose
    ``persons`` list names a character whose visual description (from the
    ``characters`` manifest) does not appear in the segment description.

    The injection is appended as a parenthetical so it doesn't break the
    narrative flow, e.g.:

        "Alice walks into the park."
        →
        "Alice (tall woman with dark brown hair, red jacket as seen in the
        reference photo) walks into the park."
    """
    characters: dict[str, str] = result.get("characters") or {}
    if not characters:
        return

    for seg in result.get("segments", []):
        persons: list[str] = seg.get("persons") or []
        if not persons:
            continue

        description: str = seg.get("description", "")
        description_lower = description.lower()

        for person_name in persons:
            char_desc = characters.get(person_name)
            if not char_desc:
                continue

            name_lower = person_name.lower()

            # Check if the character's name is even mentioned in the segment
            if name_lower not in description_lower:
                continue

            # Check if the segment already contains the character's visual
            # description.  We use two checks:
            # 1. The manifest description (or a significant portion) already
            #    appears verbatim in the segment text.
            # 2. "as seen in the reference photo" appears anywhere in the
            #    segment with the character's name also present.
            # Either match means the description is already there.
            if _segment_already_has_char_description(
                description_lower, name_lower, char_desc.lower()
            ):
                continue

            # Inject the character description after the first mention of
            # the character's name in the description.
            inject_desc = f"{char_desc}"
            if "as seen in the reference photo" not in inject_desc.lower():
                inject_desc += " as seen in the reference photo"

            description = _inject_description_after_name(
                description, person_name, inject_desc
            )
            seg["description"] = description
            # Update for subsequent person checks in the same segment
            description_lower = description.lower()
            logger.info(
                "Injected character description for '%s' into segment %s",
                person_name,
                seg.get("sequence_number", "?"),
            )


def _segment_already_has_char_description(
    description_lower: str, name_lower: str, char_desc_lower: str
) -> bool:
    """Return True if the segment description already contains the character's
    visual description from the manifest (or a substantial portion of it).

    Uses three complementary checks — any one passing is sufficient:

    1. **Verbatim match**: the full manifest description appears in the text.
    2. **Key-traits match**: at least 60 % of the significant multi-word
       phrases from the manifest description appear in the segment text.
    3. **Photo-ref phrase**: ``"as seen in the reference photo"`` appears in
       the text *and* the character name is also present (already guaranteed
       by the caller, but we re-check for safety).
    """
    # 1. Full manifest description already in segment text
    if char_desc_lower in description_lower:
        return True

    # 2. Extract key descriptive phrases (3+ word spans between commas/ands)
    #    and check how many appear in the description.
    # Strip the trailing "as seen in the reference photo" before splitting to
    # avoid counting it as a trait.
    traits_text = char_desc_lower.replace("as seen in the reference photo", "").strip()
    # Split on commas and " and " to get individual trait phrases
    raw_traits = re.split(r",| and ", traits_text)
    traits = [t.strip() for t in raw_traits if len(t.strip()) >= 6]
    if traits:
        matched = sum(1 for t in traits if t in description_lower)
        if matched / len(traits) >= 0.6:
            return True

    # 3. The "as seen in the reference photo" phrase appears *after* this
    #    character's name (not just anywhere in the segment — another character
    #    might have it).  Search from each occurrence of the name.
    phrase = "as seen in the reference photo"
    search_start = 0
    while True:
        name_pos = description_lower.find(name_lower, search_start)
        if name_pos == -1:
            break
        # Look for the phrase between this name mention and the next name
        # mention (or end of text), to scope it to this character.
        after_name = name_pos + len(name_lower)
        # Use a generous window — long descriptions can be 500+ chars
        window_end = min(after_name + 600, len(description_lower))
        window = description_lower[after_name:window_end]
        if phrase in window:
            return True
        search_start = after_name

    return False


def _inject_description_after_name(
    description: str, person_name: str, char_desc: str
) -> str:
    """Inject a character description after the first mention of person_name.

    Handles case-insensitive matching while preserving the original case of
    the name in the text.
    """
    pattern = re.compile(re.escape(person_name), re.IGNORECASE)
    match = pattern.search(description)
    if not match:
        return description

    # Insert after the matched name: "Alice" → "Alice (description)"
    insert_pos = match.end()
    # If followed by a comma or space + descriptor already, inject as parenthetical
    injected = f"{description[:insert_pos]} ({char_desc}){description[insert_pos:]}"
    return injected


async def moderate_and_split(
    scenario_text: str,
    person_names: list[str] | None = None,
    photo_paths: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Moderate scenario content and split into segments using Gemini.

    Args:
        scenario_text: The raw scenario text to moderate and split.
        person_names: Known person names from uploaded photos. None = no persons.
        photo_paths: Mapping of person_name → list of photo file paths for
                     multimodal analysis. When provided, Gemini sees the actual
                     photos and describes characters accurately.

    Returns:
        Dict with keys: approved (bool), rejection_reason (str|None),
        characters (dict), segments (list of {sequence_number, description, persons}).

    Raises:
        RuntimeError: If Gemini API call fails.
        ValueError: If response cannot be parsed.
    """
    # Build the characters section only when person_names is non-empty
    images: list[tuple[str, Image.Image]] | None = None
    if person_names:
        if photo_paths:
            # Use the photo-aware prompt that instructs Gemini to describe
            # characters from the attached reference images
            characters_section = _CHARACTERS_SECTION_WITH_PHOTOS.format(
                person_names_csv=", ".join(person_names),
            )
            images = _load_photo_images(photo_paths)
            if not images:
                # Fallback if all photos failed to load
                characters_section = _CHARACTERS_SECTION_NO_PHOTOS.format(
                    person_names_csv=", ".join(person_names),
                )
                images = None
        else:
            characters_section = _CHARACTERS_SECTION_NO_PHOTOS.format(
                person_names_csv=", ".join(person_names),
            )
    else:
        characters_section = ""

    prompt = MODERATION_SPLIT_PROMPT.format(
        scenario_text=scenario_text,
        characters_section=characters_section,
    )

    logger.info(
        "Sending moderation request to Gemini | "
        "scenario_length=%d person_names=%s photos=%s",
        len(scenario_text),
        person_names or [],
        bool(images),
    )
    logger.info("Gemini prompt:\n%s", prompt)

    raw_response = await _call_gemini(prompt, images=images)

    logger.debug("Gemini raw response:\n%s", raw_response)

    result = parse_gemini_response(raw_response, person_names=person_names)

    logger.info(
        "Gemini moderation result | approved=%s segments=%d characters=%s",
        result["approved"],
        len(result.get("segments", [])),
        list(result.get("characters", {}).keys()),
    )

    return result
