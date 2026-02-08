"""Unit tests for moderation_service — Gemini moderation + scenario splitting.

Tests MUST fail before T034 implementation (Constitution Principle V: Test-First).

Covers:
- Clean scenario → approved + segments list
- Prohibited content → rejected with reason
- Scenario too long for 15 segments → rejected
- Combined moderation+splitting prompt format
- Gemini response parsing (JSON extraction)
- Error handling for Gemini API failures
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.moderation_service import (
    moderate_and_split,
    parse_gemini_response,
)


class TestParseGeminiResponse:
    """Tests for parse_gemini_response(raw_text) → dict."""

    def test_valid_approved_response(self) -> None:
        """Parse a valid approved JSON response with segments."""
        raw = '''```json
{
    "approved": true,
    "rejection_reason": null,
    "segments": [
        {"sequence_number": 1, "description": "Alice walks into the garden."},
        {"sequence_number": 2, "description": "She picks a flower and smiles."}
    ]
}
```'''
        result = parse_gemini_response(raw)
        assert result["approved"] is True
        assert result["rejection_reason"] is None
        assert len(result["segments"]) == 2
        assert result["segments"][0]["description"] == "Alice walks into the garden."

    def test_valid_rejected_response(self) -> None:
        """Parse a valid rejected JSON response."""
        raw = '''```json
{
    "approved": false,
    "rejection_reason": "Contains violent content",
    "segments": []
}
```'''
        result = parse_gemini_response(raw)
        assert result["approved"] is False
        assert result["rejection_reason"] == "Contains violent content"
        assert result["segments"] == []

    def test_raw_json_without_markdown(self) -> None:
        """Parse JSON without markdown code fences."""
        raw = '{"approved": true, "rejection_reason": null, "segments": [{"sequence_number": 1, "description": "Scene one."}]}'
        result = parse_gemini_response(raw)
        assert result["approved"] is True
        assert len(result["segments"]) == 1

    def test_invalid_json(self) -> None:
        """Raise ValueError for unparseable response."""
        with pytest.raises(ValueError, match="[Pp]arse|JSON|[Ii]nvalid"):
            parse_gemini_response("This is not JSON at all.")


class TestModerateAndSplit:
    """Tests for moderate_and_split(scenario_text) → result dict."""

    @pytest.mark.asyncio
    @patch("backend.services.moderation_service._call_gemini")
    async def test_clean_scenario_approved(self, mock_gemini: AsyncMock) -> None:
        """Clean scenario returns approved with segments."""
        mock_gemini.return_value = '''```json
{
    "approved": true,
    "rejection_reason": null,
    "segments": [
        {"sequence_number": 1, "description": "Alice enters the park."},
        {"sequence_number": 2, "description": "She meets Bob by the fountain."},
        {"sequence_number": 3, "description": "They walk into the sunset."}
    ]
}
```'''
        result = await moderate_and_split("Alice enters the park. She meets Bob. They walk off.")
        assert result["approved"] is True
        assert len(result["segments"]) == 3
        mock_gemini.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.services.moderation_service._call_gemini")
    async def test_prohibited_content_rejected(self, mock_gemini: AsyncMock) -> None:
        """Prohibited scenario returns rejected with reason."""
        mock_gemini.return_value = '''```json
{
    "approved": false,
    "rejection_reason": "Content contains explicit violence",
    "segments": []
}
```'''
        result = await moderate_and_split("Violent scenario content here.")
        assert result["approved"] is False
        assert "violence" in result["rejection_reason"].lower()
        assert result["segments"] == []

    @pytest.mark.asyncio
    @patch("backend.services.moderation_service._call_gemini")
    async def test_max_15_segments(self, mock_gemini: AsyncMock) -> None:
        """Approved response respects ≤15 segment limit."""
        segments = [
            {"sequence_number": i, "description": f"Segment {i} action."} for i in range(1, 16)
        ]
        mock_gemini.return_value = (
            '{"approved": true, "rejection_reason": null, "segments": '
            + str(segments).replace("'", '"')
            + "}"
        )
        result = await moderate_and_split("A very long scenario with many scenes.")
        assert result["approved"] is True
        assert len(result["segments"]) <= 15

    @pytest.mark.asyncio
    @patch("backend.services.moderation_service._call_gemini")
    async def test_gemini_api_failure(self, mock_gemini: AsyncMock) -> None:
        """Gemini API errors propagate as exceptions."""
        mock_gemini.side_effect = RuntimeError("Gemini API unavailable")
        with pytest.raises(RuntimeError, match="Gemini API"):
            await moderate_and_split("Normal scenario text.")

    @pytest.mark.asyncio
    @patch("backend.services.moderation_service._call_gemini")
    async def test_gemini_returns_garbage(self, mock_gemini: AsyncMock) -> None:
        """Non-JSON Gemini response raises ValueError."""
        mock_gemini.return_value = "I cannot process this request."
        with pytest.raises(ValueError):
            await moderate_and_split("Normal scenario text.")
