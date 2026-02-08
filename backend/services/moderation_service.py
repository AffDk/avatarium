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

RESPOND WITH VALID JSON ONLY (no extra text):
{{
    "approved": true/false,
    "rejection_reason": null or "reason string",
    "segments": [
        {{"sequence_number": 1, "description": "Scene description..."}},
        ...
    ]
}}

If rejected, segments should be an empty array.
If approved, provide 1-15 segments covering the full scenario.
"""


async def _call_gemini(prompt: str) -> str:
    """Call Gemini and return the text response.

    This function is separated for easy mocking in tests.
    """
    model = genai.GenerativeModel(settings.gemini_model)
    response = await model.generate_content_async(prompt)
    return response.text


def parse_gemini_response(raw_text: str) -> dict[str, Any]:
    """Parse Gemini's JSON response, handling markdown code fences.

    Args:
        raw_text: Raw response from Gemini (may be wrapped in ```json ... ```)

    Returns:
        Parsed dict with keys: approved, rejection_reason, segments

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

    return result


async def moderate_and_split(scenario_text: str) -> dict[str, Any]:
    """Moderate scenario content and split into segments using Gemini.

    Args:
        scenario_text: The raw scenario text to moderate and split.

    Returns:
        Dict with keys: approved (bool), rejection_reason (str|None),
        segments (list of {sequence_number, description}).

    Raises:
        RuntimeError: If Gemini API call fails.
        ValueError: If response cannot be parsed.
    """
    prompt = MODERATION_SPLIT_PROMPT.format(scenario_text=scenario_text)
    raw_response = await _call_gemini(prompt)
    return parse_gemini_response(raw_response)
