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

import json
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

    # ── T001: Backward compatibility — no person_names ──────────────────
    @pytest.mark.asyncio
    @patch("backend.services.moderation_service._call_gemini")
    async def test_backward_compat_no_person_names(self, mock_gemini: AsyncMock) -> None:
        """Calling without person_names preserves existing behaviour (FR-009).

        characters defaults to {} and each segment.persons defaults to [].
        """
        mock_gemini.return_value = '{"approved": true, "rejection_reason": null, "segments": [{"sequence_number": 1, "description": "A cat sits on a windowsill."}]}'
        result = await moderate_and_split("A cat sits on a windowsill watching birds.")
        assert result["approved"] is True
        assert result.get("characters") == {}
        for seg in result["segments"]:
            assert seg.get("persons") == []

    # ── T002: Person names included in prompt ───────────────────────────
    @pytest.mark.asyncio
    @patch("backend.services.moderation_service._call_gemini")
    async def test_person_names_included_in_prompt(self, mock_gemini: AsyncMock) -> None:
        """Person names are injected into the Gemini prompt."""
        mock_gemini.return_value = '{"approved": true, "rejection_reason": null, "characters": {"alice": "tall woman", "bob": "short man"}, "segments": [{"sequence_number": 1, "description": "Alice waves.", "persons": ["alice", "bob"]}]}'
        await moderate_and_split(
            "Alice and Bob meet.", person_names=["alice", "bob"]
        )
        prompt_sent = mock_gemini.call_args[0][0]
        assert "alice" in prompt_sent.lower()
        assert "bob" in prompt_sent.lower()

    # ── T003: Empty person_names treated as None ────────────────────────
    @pytest.mark.asyncio
    @patch("backend.services.moderation_service._call_gemini")
    async def test_empty_person_names_treated_as_none(self, mock_gemini: AsyncMock) -> None:
        """Empty list behaves like None — no characters section in prompt."""
        mock_gemini.return_value = '{"approved": true, "rejection_reason": null, "segments": [{"sequence_number": 1, "description": "Scene one."}]}'
        await moderate_and_split("A bird flies.", person_names=[])
        prompt_sent = mock_gemini.call_args[0][0]
        # Should NOT contain the characters block header
        assert "CHARACTERS" not in prompt_sent
        result = await moderate_and_split("A bird flies.", person_names=[])
        assert result.get("characters") == {}
        for seg in result["segments"]:
            assert seg.get("persons") == []

    # ── T007: Person-aware descriptions contain names (FR-006) ──────────
    @pytest.mark.asyncio
    @patch("backend.services.moderation_service._call_gemini")
    async def test_person_aware_descriptions_contain_names(
        self, mock_gemini: AsyncMock
    ) -> None:
        """Each segment description mentions at least one person name."""
        mock_gemini.return_value = json.dumps({
            "approved": True,
            "rejection_reason": None,
            "characters": {
                "alice": "tall woman with curly red hair and a green dress",
                "bob": "stocky man with round glasses and a blue denim jacket",
            },
            "segments": [
                {
                    "sequence_number": 1,
                    "description": "Alice, a tall woman with curly red hair and a green dress, walks into the park.",
                    "persons": ["alice"],
                },
                {
                    "sequence_number": 2,
                    "description": "Alice waves to Bob, a stocky man with round glasses and a blue denim jacket.",
                    "persons": ["alice", "bob"],
                },
            ],
        })
        result = await moderate_and_split(
            "Alice enters the park. She waves to Bob.",
            person_names=["alice", "bob"],
        )
        for seg in result["segments"]:
            desc_lower = seg["description"].lower()
            assert any(
                name in desc_lower for name in ["alice", "bob"]
            ), f"Segment {seg['sequence_number']} missing person name: {seg['description']}"

    # ── T008: Characters manifest maps all persons (FR-011, FR-012) ─────
    @pytest.mark.asyncio
    @patch("backend.services.moderation_service._call_gemini")
    async def test_characters_manifest_maps_all_persons(
        self, mock_gemini: AsyncMock
    ) -> None:
        """Characters manifest contains entries for every provided person name."""
        mock_gemini.return_value = json.dumps({
            "approved": True,
            "rejection_reason": None,
            "characters": {
                "alice": "tall woman with curly red hair",
                "bob": "stocky man with round glasses",
            },
            "segments": [
                {
                    "sequence_number": 1,
                    "description": "Alice and Bob stand together.",
                    "persons": ["alice", "bob"],
                },
            ],
        })
        result = await moderate_and_split(
            "Alice and Bob stand together.",
            person_names=["alice", "bob"],
        )
        characters = result["characters"]
        assert "alice" in characters
        assert "bob" in characters
        assert isinstance(characters["alice"], str)
        assert len(characters["alice"]) > 0
        assert isinstance(characters["bob"], str)
        assert len(characters["bob"]) > 0

    # ── T009: Single person in every segment (SC-005) ───────────────────
    @pytest.mark.asyncio
    @patch("backend.services.moderation_service._call_gemini")
    async def test_single_person_in_every_segment(
        self, mock_gemini: AsyncMock
    ) -> None:
        """Single-person project: every segment references that person."""
        mock_gemini.return_value = json.dumps({
            "approved": True,
            "rejection_reason": None,
            "characters": {
                "charlie": "young man with a leather jacket and dark sunglasses",
            },
            "segments": [
                {
                    "sequence_number": 1,
                    "description": "Charlie, a young man with a leather jacket, walks down the street.",
                    "persons": ["charlie"],
                },
                {
                    "sequence_number": 2,
                    "description": "Charlie pauses at a shop window and adjusts his dark sunglasses.",
                    "persons": ["charlie"],
                },
                {
                    "sequence_number": 3,
                    "description": "Charlie enters the coffee shop and sits by the window.",
                    "persons": ["charlie"],
                },
            ],
        })
        result = await moderate_and_split(
            "Charlie walks to a coffee shop.",
            person_names=["charlie"],
        )
        assert len(result["segments"]) == 3
        for seg in result["segments"]:
            assert "charlie" in seg["description"].lower()
            assert "charlie" in seg["persons"]


class TestParseGeminiResponsePersonValidation:
    """Tests for person-aware validation in parse_gemini_response() (US3)."""

    # ── T012: Validate characters manifest (FR-014) ─────────────────────
    def test_parse_validates_characters_manifest_valid(self) -> None:
        """Valid characters dict is accepted."""
        raw = json.dumps({
            "approved": True,
            "rejection_reason": None,
            "characters": {"alice": "tall woman", "bob": "short man"},
            "segments": [
                {"sequence_number": 1, "description": "Scene.", "persons": ["alice"]},
            ],
        })
        result = parse_gemini_response(raw, person_names=["alice", "bob"])
        assert result["characters"] == {"alice": "tall woman", "bob": "short man"}

    def test_parse_validates_characters_manifest_list_raises(self) -> None:
        """Characters as a list raises ValueError."""
        raw = json.dumps({
            "approved": True,
            "rejection_reason": None,
            "characters": ["alice", "bob"],
            "segments": [
                {"sequence_number": 1, "description": "Scene.", "persons": ["alice"]},
            ],
        })
        with pytest.raises(ValueError, match="characters"):
            parse_gemini_response(raw, person_names=["alice", "bob"])

    def test_parse_validates_characters_manifest_non_string_values(self) -> None:
        """Characters with non-string values raises ValueError."""
        raw = json.dumps({
            "approved": True,
            "rejection_reason": None,
            "characters": {"alice": 123, "bob": True},
            "segments": [
                {"sequence_number": 1, "description": "Scene.", "persons": ["alice"]},
            ],
        })
        with pytest.raises(ValueError, match="characters"):
            parse_gemini_response(raw, person_names=["alice", "bob"])

    # ── T013: Validate persons array (FR-008) ───────────────────────────
    def test_parse_validates_persons_array_valid(self) -> None:
        """Valid persons arrays pass validation."""
        raw = json.dumps({
            "approved": True,
            "rejection_reason": None,
            "characters": {"alice": "tall woman"},
            "segments": [
                {"sequence_number": 1, "description": "Scene.", "persons": ["alice"]},
            ],
        })
        result = parse_gemini_response(raw, person_names=["alice"])
        assert result["segments"][0]["persons"] == ["alice"]

    def test_parse_validates_persons_as_string_raises(self) -> None:
        """Persons as a string (not list) raises ValueError."""
        raw = json.dumps({
            "approved": True,
            "rejection_reason": None,
            "characters": {"alice": "tall woman"},
            "segments": [
                {"sequence_number": 1, "description": "Scene.", "persons": "alice"},
            ],
        })
        with pytest.raises(ValueError, match="persons"):
            parse_gemini_response(raw, person_names=["alice"])

    def test_parse_validates_persons_non_string_entries_raises(self) -> None:
        """Persons with non-string entries raises ValueError."""
        raw = json.dumps({
            "approved": True,
            "rejection_reason": None,
            "characters": {"alice": "tall woman"},
            "segments": [
                {"sequence_number": 1, "description": "Scene.", "persons": [123]},
            ],
        })
        with pytest.raises(ValueError, match="persons"):
            parse_gemini_response(raw, person_names=["alice"])

    # ── T014: Person names normalized to lowercase (FR-010) ─────────────
    def test_persons_normalized_to_lowercase(self) -> None:
        """Persons entries are normalized to lowercase."""
        raw = json.dumps({
            "approved": True,
            "rejection_reason": None,
            "characters": {"alice": "tall woman", "bob": "short man"},
            "segments": [
                {"sequence_number": 1, "description": "Scene.", "persons": ["Alice", "BOB"]},
            ],
        })
        result = parse_gemini_response(raw, person_names=["alice", "bob"])
        assert result["segments"][0]["persons"] == ["alice", "bob"]

    # ── T015: Unknown persons filtered out (FR-005) ─────────────────────
    def test_unknown_persons_filtered_out(self) -> None:
        """Persons not in the known list are removed."""
        raw = json.dumps({
            "approved": True,
            "rejection_reason": None,
            "characters": {"alice": "tall woman"},
            "segments": [
                {
                    "sequence_number": 1,
                    "description": "Scene with alice and charlie.",
                    "persons": ["alice", "charlie"],
                },
            ],
        })
        result = parse_gemini_response(raw, person_names=["alice", "bob"])
        assert result["segments"][0]["persons"] == ["alice"]

    # ── T016: Characters defaults empty when no persons (FR-007) ────────
    def test_characters_defaults_empty_when_no_persons(self) -> None:
        """Without person_names, characters defaults to {} and persons to []."""
        raw = json.dumps({
            "approved": True,
            "rejection_reason": None,
            "segments": [
                {"sequence_number": 1, "description": "A cat sleeps."},
            ],
        })
        result = parse_gemini_response(raw)
        assert result["characters"] == {}
        for seg in result["segments"]:
            assert seg["persons"] == []

    # ── T024: Persons inferred when not named in scenario (Edge Case 2) ─
    @pytest.mark.asyncio
    @patch("backend.services.moderation_service._call_gemini")
    async def test_persons_inferred_when_not_named_in_scenario(
        self, mock_gemini: AsyncMock
    ) -> None:
        """Person names appear in prompt even if scenario uses generic terms."""
        mock_gemini.return_value = json.dumps({
            "approved": True,
            "rejection_reason": None,
            "characters": {"alice": "tall woman"},
            "segments": [
                {
                    "sequence_number": 1,
                    "description": "Alice, a tall woman, walks down the road.",
                    "persons": ["alice"],
                },
            ],
        })
        await moderate_and_split(
            "A person walks down the road.",
            person_names=["alice"],
        )
        prompt_sent = mock_gemini.call_args[0][0]
        # Even though scenario says "a person", the prompt still includes "alice"
        assert "alice" in prompt_sent.lower()

    # ── T025: Rejected scenario with person_names (FR-009, Edge Case 5) ─
    @pytest.mark.asyncio
    @patch("backend.services.moderation_service._call_gemini")
    async def test_rejected_scenario_with_person_names(
        self, mock_gemini: AsyncMock
    ) -> None:
        """Rejected scenario preserves rejection even when person_names given."""
        mock_gemini.return_value = json.dumps({
            "approved": False,
            "rejection_reason": "Content contains explicit violence",
            "characters": {},
            "segments": [],
        })
        result = await moderate_and_split(
            "Violent scenario content.",
            person_names=["alice", "bob"],
        )
        assert result["approved"] is False
        assert "violence" in result["rejection_reason"].lower()
        assert result["characters"] == {}
        assert result["segments"] == []
