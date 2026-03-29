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
- IMPORTANT: Each segment description will be used as a TEXT PROMPT for an AI video generation model that is also given the character reference photos as input images. The model will try to generate characters that match the reference photos, but it relies on the text prompt to reinforce which characters to show and what they look like. Therefore you MUST describe each character's appearance from their reference photos in EVERY segment — this is how the video model knows which person in the reference photos corresponds to which character in the scene.

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

DETAILED SCENE DESCRIPTION & SPATIAL CONTINUITY RULES:
Each segment description MUST include ALL of the following elements to ensure the video generation model produces realistic, consistent output:

1. ENVIRONMENT DESCRIPTION: Name and describe the specific location (e.g., "a sunlit suburban kitchen with white tile flooring, oak cabinets, and a window above the sink"). The environment MUST remain consistent across consecutive segments set in the same location — do NOT change the room layout, furniture, or architectural features unless the character moves to a new space.

2. CAMERA ANGLE: Specify the camera perspective for each segment (e.g., "medium shot from waist up", "wide establishing shot", "close-up on face", "over-the-shoulder shot"). Camera angles should transition logically between segments — avoid jarring jumps from extreme close-up to wide shot without motivation.

3. LIGHTING: Describe the lighting conditions (e.g., "warm afternoon sunlight streaming through the window", "dim overhead fluorescent light", "soft golden-hour backlight"). Lighting MUST stay consistent across segments set in the same time and place unless there is a narrative reason for change (e.g., someone turns off a light, the sun sets).

4. CHARACTER POSITIONS: Describe WHERE each character is within the environment relative to landmarks and other characters (e.g., "Alice stands behind the kitchen counter, facing Bob who sits on the stool across from her"). Do NOT use abstract frame positions like "on the left side" or "center frame" — use environmental references instead.

5. PROP AND OBJECT CONTINUITY: If a character is holding or using an object (e.g., a coffee mug, a phone, a bag), that object MUST persist across segments until the character explicitly puts it down or hands it off. Do not have objects appear or disappear between segments.

6. TRANSITION DESCRIPTION: The FIRST sentence of each segment (except segment 1) MUST describe how the scene connects to the previous segment. Examples: "Continuing from the same position at the kitchen counter, Alice...", "As Bob finishes speaking, the camera shifts to show Alice who is now standing near the doorway...". Never start a segment as if it's an independent scene.

7. BACKGROUND ACTIVITY: Include subtle environmental details that ground the scene in reality — e.g., "leaves gently blowing in the background", "the clock on the wall shows 3:15", "traffic barely audible through the closed window". These details should remain consistent across segments.

SCENARIO:
{scenario_text}
{characters_section}
RESPOND WITH VALID JSON ONLY (no extra text):
{{
    "approved": true/false,
    "rejection_reason": null or "reason string",
    "characters": {{}},
    "environment": "A one-paragraph description of the primary setting/location shared across segments (e.g., 'A cozy suburban kitchen with white tile floors, wooden cabinets, a window above the sink, and a small breakfast table with two stools.'). This anchors spatial consistency.",
    "segments": [
        {{"sequence_number": 1, "description": "Full scene description including environment, camera angle, lighting, character positions, and action...", "persons": []}},
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

CRITICAL — CHARACTER IDENTIFICATION RULES:
The video generation model that will process these segments receives the actual reference photos as input images. However, when multiple people appear in the reference photos, the model needs a BRIEF distinguishing description to know which person in the photo corresponds to which character name. Without this, the model may confuse characters (e.g., swapping a toddler for a woman).

Your job is to provide a SHORT identifying tag for each character — just enough to disambiguate them from each other in the reference photos.

RULES:
- In the "characters" JSON field, map each name to a BRIEF identifying description (3-6 words): e.g., "young toddler boy", "adult woman with red jacket", "tall man with glasses". Focus on the MOST distinguishing traits that separate this person from the other characters — such as age group, gender, and one standout visual feature.
- In EVERY segment description, identify each character with their name followed by their brief tag and "reference photo" in parentheses — e.g., "Alice (adult woman, reference photo) walks into the park." or "Bob (toddler boy, reference photo) toddles behind her."
- The tag MUST be short enough to disambiguate but NOT a full physical inventory. Do NOT list every detail like hair color, skin tone, eye shape, clothing, accessories, build, etc.
- WRONG (too verbose): "Person1, a young adult woman with medium skin tone, long straight dark brown hair with a white orchid clip, dark eyebrows, red lipstick, wearing a white lace top and silver earrings as seen in the reference photo, walks through the terminal."
- WRONG (too minimal — no disambiguation): "Person1 (reference photo) walks through the terminal."
- CORRECT: "Person1 (young woman with dark hair, reference photo) walks purposefully from right to left through the brightly lit terminal, carrying a small bag over her shoulder."
- Even if a character appeared in a previous segment, you MUST include their identifying tag and "reference photo" in EVERY segment. The video model processes each segment independently.
- Focus your segment text on ACTION, MOVEMENT, ENVIRONMENT, CAMERA ANGLE, and LIGHTING — the brief tag handles identification, and the reference photo handles full appearance.
- Describe spatial relationships between characters (e.g., "Alice stands facing Bob") — do NOT use frame positions like "left of frame".
- Each segment's "persons" array MUST list only the character names who appear in that segment (lowercase).
- Only use character names from the list above — do NOT invent new character names.

EXAMPLE OUTPUT (with characters):
{{
    "approved": true,
    "rejection_reason": null,
    "characters": {{
        "alice": "adult woman with red jacket",
        "bob": "tall man with round glasses"
    }},
    "environment": "A quiet public park on a sunny afternoon, with a gravel walking path flanked by tall oak trees, wooden benches on the left side, and a small pond visible in the background.",
    "segments": [
        {{"sequence_number": 1, "description": "Wide establishing shot of a quiet public park on a sunny afternoon, warm golden-hour sunlight filtering through tall oak trees lining a gravel path. Alice (adult woman with red jacket, reference photo) walks left to right along the gravel path, passing a wooden bench on her left. Leaves drift gently in a light breeze.", "persons": ["alice"]}},
        {{"sequence_number": 2, "description": "Continuing along the same gravel path from the previous shot, medium shot with warm afternoon sunlight. Alice (adult woman with red jacket, reference photo) continues walking left to right and raises her right hand to wave toward Bob (tall man with round glasses, reference photo), who stands near a wooden bench about ten meters ahead and turns to face her. The pond is visible in the background behind Bob.", "persons": ["alice", "bob"]}}
    ]
}}

NOTICE how each character name is always followed by a short identifying tag + "reference photo" in parentheses. This helps the video model match each character name to the correct person in the reference photos.
"""

_CHARACTERS_SECTION_NO_PHOTOS = """
CHARACTERS (known persons from uploaded photos):
{person_names_csv}

CRITICAL — CHARACTER IDENTIFICATION RULES:
The video generation model that will process these segments receives the actual reference photos as input images. However, when multiple people appear, the model needs a BRIEF distinguishing description to know which person corresponds to which character name.

RULES:
- In the "characters" JSON field, map each name to a BRIEF identifying description (3-6 words): e.g., "adult woman with green dress", "tall man with round glasses".
- In EVERY segment description, identify each character with their name followed by their brief tag and "reference photo" in parentheses — e.g., "Alice (adult woman, reference photo) walks into the park."
- Keep the tag short — just enough to disambiguate characters from each other.
- Focus segment text on ACTION, MOVEMENT, ENVIRONMENT, CAMERA ANGLE, and LIGHTING.
- Even if a character appeared in a previous segment, you MUST include their identifying tag and "reference photo" in EVERY segment.
- Describe spatial relationships between characters — do NOT use frame positions like "left of frame".
- Each segment's "persons" array MUST list only the character names who appear in that segment (lowercase).
- Only use character names from the list above — do NOT invent new character names.

EXAMPLE OUTPUT (with characters):
{{
    "approved": true,
    "rejection_reason": null,
    "characters": {{
        "alice": "adult woman with green dress",
        "bob": "tall man with round glasses"
    }},
    "environment": "A quiet public park on a sunny afternoon, with a gravel walking path flanked by tall oak trees, wooden benches on the left side, and a small pond visible in the background.",
    "segments": [
        {{"sequence_number": 1, "description": "Wide establishing shot of a quiet public park on a sunny afternoon, warm golden-hour sunlight filtering through tall oak trees. Alice (adult woman with green dress, reference photo) walks left to right along the gravel path, passing a wooden bench on her left.", "persons": ["alice"]}},
        {{"sequence_number": 2, "description": "Continuing along the same gravel path from the previous shot, medium shot with warm afternoon sunlight. Alice (adult woman with green dress, reference photo) continues left to right and waves to Bob (tall man with round glasses, reference photo), who stands near a bench about ten meters ahead.", "persons": ["alice", "bob"]}}
    ]
}}

NOTICE how each character name includes a short identifying tag + "reference photo" to help the video model match names to the correct person.
"""

_CHARACTERS_SECTION_WITH_DESCRIPTIONS = """
CHARACTERS (with user-provided visual descriptions — no photos attached):
{character_descriptions_text}

CRITICAL — CHARACTER IDENTIFICATION RULES:
The user has described each person above. Use these descriptions to write segment descriptions that help the video model render each character correctly.

RULES:
- In the "characters" JSON field, map each name to a BRIEF identifying tag (3-6 words) derived from the user description: e.g., "adult woman with red jacket", "young toddler boy".
- In EVERY segment description, identify each character with their name followed by their brief tag and "reference photo" in parentheses — e.g., "Alice (adult woman with red jacket, reference photo) walks into the park."
- Keep the tag short — just enough to distinguish characters from each other.
- Focus segment text on ACTION, MOVEMENT, ENVIRONMENT, CAMERA ANGLE, and LIGHTING.
- Even if a character appeared in a previous segment, you MUST include their identifying tag and "reference photo" in EVERY segment.
- Describe spatial relationships between characters — do NOT use frame positions like "left of frame".
- Each segment's "persons" array MUST list only the character names who appear in that segment (lowercase).
- Only use character names from the list above — do NOT invent new character names.
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
        logger.info("[Gemini] Sending multimodal request to %s with %d reference photos",
                     settings.gemini_model, len(images))
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
    """Ensure every character mention in segments has an identifying tag + '(reference photo)'.

    Gemini sometimes omits the identifying tag or ``(reference photo)`` after
    character names despite explicit instructions.  This function patches any
    segment where a character from the ``persons`` list is mentioned by name
    but lacks the tag.  It uses the ``characters`` manifest to inject the
    brief identifier (e.g., "toddler boy") so the video model can
    disambiguate who is who.

    Example:

        "Alice walks into the park."
        →  (with characters={"alice": "adult woman with red jacket"})
        "Alice (adult woman with red jacket, reference photo) walks into the park."
    """
    characters_manifest: dict[str, str] = result.get("characters") or {}

    for seg in result.get("segments", []):
        persons: list[str] = seg.get("persons") or []
        if not persons:
            continue

        description: str = seg.get("description", "")
        description_lower = description.lower()

        for person_name in persons:
            name_lower = person_name.lower()

            # Check if the character's name is even mentioned in the segment
            if name_lower not in description_lower:
                continue

            # Check if the segment already has a reference-photo marker
            if _segment_has_reference_photo_tag(description_lower, name_lower):
                continue

            # Build the tag: "brief identifier, reference photo" or just "reference photo"
            char_desc = characters_manifest.get(name_lower, "")
            tag = f"{char_desc}, reference photo" if char_desc else "reference photo"

            # Inject after the first mention of the name
            description = _inject_description_after_name(
                description, person_name, tag
            )
            seg["description"] = description
            # Update for subsequent person checks in the same segment
            description_lower = description.lower()
            logger.info(
                "Injected (%s) tag for '%s' into segment %s",
                tag,
                person_name,
                seg.get("sequence_number", "?"),
            )


def _segment_has_reference_photo_tag(
    description_lower: str, name_lower: str
) -> bool:
    """Return True if a reference-photo marker appears after the character name.

    Accepts either of the two forms:
    - ``(reference photo)`` — the preferred concise format
    - ``as seen in the reference photo`` — legacy verbose format
    """
    markers = ["(reference photo)", "as seen in the reference photo"]
    search_start = 0
    while True:
        name_pos = description_lower.find(name_lower, search_start)
        if name_pos == -1:
            break
        after_name = name_pos + len(name_lower)
        # Check a reasonable window after the name
        window_end = min(after_name + 200, len(description_lower))
        window = description_lower[after_name:window_end]
        for marker in markers:
            if marker in window:
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
    person_descriptions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Moderate scenario content and split into segments using Gemini.

    Args:
        scenario_text: The raw scenario text to moderate and split.
        person_names: Known person names from uploaded photos. None = no persons.
        photo_paths: Mapping of person_name → list of photo file paths for
                     multimodal analysis. Skipped when person_descriptions covers
                     all persons (saves multimodal token cost).
        person_descriptions: User-provided visual descriptions per person
                             (name → description). When provided for all persons,
                             replaces photo-based analysis entirely.

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
        all_described = (
            person_descriptions is not None
            and all(n in person_descriptions or n.lower() in person_descriptions
                    for n in person_names)
        )
        if all_described and person_descriptions:
            # Use user-provided descriptions — no photo upload needed
            desc_lines = "\n".join(
                f"- {name}: {person_descriptions.get(name) or person_descriptions.get(name.lower(), '')}"
                for name in person_names
            )
            characters_section = _CHARACTERS_SECTION_WITH_DESCRIPTIONS.format(
                character_descriptions_text=desc_lines,
            )
            images = None
            logger.info("[Gemini] Using user-provided descriptions for %d person(s) — skipping photos", len(person_names))
        elif photo_paths:
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
        "[Gemini] ─── moderation + splitting ───\n"
        "  model: %s\n"
        "  scenario length: %d chars\n"
        "  person names: %s\n"
        "  reference photos attached: %s\n"
        "  photo count: %d",
        settings.gemini_model,
        len(scenario_text),
        person_names or [],
        bool(images),
        len(images) if images else 0,
    )
    logger.debug("[Gemini] Full prompt:\n%s", prompt)

    raw_response = await _call_gemini(prompt, images=images)

    logger.debug("Gemini raw response:\n%s", raw_response)

    result = parse_gemini_response(raw_response, person_names=person_names)

    logger.info(
        "[Gemini] Moderation result | approved=%s segments=%d characters=%s",
        result["approved"],
        len(result.get("segments", [])),
        result.get("characters", {}),
    )

    return result
