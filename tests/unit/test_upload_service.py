"""Unit tests for upload_service — filename parsing, validation, person grouping.

Tests MUST fail before T024/T024a implementation (Constitution Principle V: Test-First).

Covers:
- parse_filename: valid patterns, case-insensitive, rejection of invalid names
- validate_file: size ≤10MB, MIME type (jpeg/png/webp only)
- group_files_by_person: correct grouping from multiple files
- validate_person_references (FR-008): scenario mentioning unknown persons → warning list
"""

import io
from unittest.mock import MagicMock

import pytest

from backend.services.upload_service import (
    group_files_by_person,
    parse_filename,
    validate_file,
    validate_person_references,
)


# ── parse_filename ────────────────────────────────────────


class TestParseFilename:
    """Tests for parse_filename(name) → (person_name, sequence_number)."""

    def test_basic_pattern(self) -> None:
        """person1_1.jpg → person='person1', seq=1."""
        person, seq = parse_filename("person1_1.jpg")
        assert person == "person1"
        assert seq == 1

    def test_multi_digit_sequence(self) -> None:
        """alice_12.png → person='alice', seq=12."""
        person, seq = parse_filename("alice_12.png")
        assert person == "alice"
        assert seq == 12

    def test_case_insensitive_normalizes_to_lowercase(self) -> None:
        """PERSON1_1.JPG → person='person1', seq=1."""
        person, seq = parse_filename("PERSON1_1.JPG")
        assert person == "person1"
        assert seq == 1

    def test_mixed_case(self) -> None:
        """Alice_3.WebP → person='alice', seq=3."""
        person, seq = parse_filename("Alice_3.WebP")
        assert person == "alice"
        assert seq == 3

    def test_person_name_with_numbers(self) -> None:
        """player42_2.jpg → person='player42', seq=2."""
        person, seq = parse_filename("player42_2.jpg")
        assert person == "player42"
        assert seq == 2

    def test_webp_extension(self) -> None:
        """bob_1.webp → person='bob', seq=1."""
        person, seq = parse_filename("bob_1.webp")
        assert person == "bob"
        assert seq == 1

    def test_invalid_no_underscore(self) -> None:
        """myphoto.jpg → raises ValueError."""
        with pytest.raises(ValueError, match="[Ii]nvalid"):
            parse_filename("myphoto.jpg")

    def test_invalid_no_sequence_number(self) -> None:
        """person_abc.jpg → raises ValueError (non-numeric sequence)."""
        with pytest.raises(ValueError, match="[Ii]nvalid"):
            parse_filename("person_abc.jpg")

    def test_invalid_no_extension(self) -> None:
        """person1_1 → raises ValueError."""
        with pytest.raises(ValueError, match="[Ii]nvalid"):
            parse_filename("person1_1")

    def test_invalid_empty_person_name(self) -> None:
        """_1.jpg → raises ValueError (empty person name)."""
        with pytest.raises(ValueError, match="[Ii]nvalid"):
            parse_filename("_1.jpg")

    def test_invalid_zero_sequence(self) -> None:
        """person1_0.jpg → raises ValueError (sequence must be ≥1)."""
        with pytest.raises(ValueError, match="[Ii]nvalid|[Ss]equence"):
            parse_filename("person1_0.jpg")

    def test_invalid_unsupported_extension(self) -> None:
        """person1_1.gif → raises ValueError (only jpeg/png/webp)."""
        with pytest.raises(ValueError, match="[Ii]nvalid|[Ee]xtension|[Uu]nsupported"):
            parse_filename("person1_1.gif")


# ── validate_file ─────────────────────────────────────────


class TestValidateFile:
    """Tests for validate_file(file) → check size ≤10MB and MIME type."""

    @staticmethod
    def _make_upload(
        filename: str = "person1_1.jpg",
        content_type: str = "image/jpeg",
        size: int = 1024,
    ) -> MagicMock:
        """Create a mock UploadFile."""
        mock = MagicMock()
        mock.filename = filename
        mock.content_type = content_type
        mock.size = size
        mock.file = io.BytesIO(b"\x00" * size)
        return mock

    def test_valid_jpeg(self) -> None:
        """Valid JPEG under 10MB should pass."""
        f = self._make_upload(content_type="image/jpeg", size=5_000_000)
        validate_file(f)  # Should not raise

    def test_valid_png(self) -> None:
        """Valid PNG should pass."""
        f = self._make_upload(content_type="image/png", size=1_000)
        validate_file(f)

    def test_valid_webp(self) -> None:
        """Valid WebP should pass."""
        f = self._make_upload(content_type="image/webp", size=1_000)
        validate_file(f)

    def test_oversized_file(self) -> None:
        """File >10MB should raise ValueError."""
        f = self._make_upload(size=10_485_761)  # 10MB + 1 byte
        with pytest.raises(ValueError, match="[Ss]ize|10.*MB|too large"):
            validate_file(f)

    def test_exactly_10mb_passes(self) -> None:
        """File exactly 10MB should pass."""
        f = self._make_upload(size=10_485_760)
        validate_file(f)

    def test_invalid_mime_type_gif(self) -> None:
        """GIF MIME type should raise ValueError."""
        f = self._make_upload(content_type="image/gif")
        with pytest.raises(ValueError, match="[Mm]ime|[Tt]ype|[Uu]nsupported"):
            validate_file(f)

    def test_invalid_mime_type_bmp(self) -> None:
        """BMP MIME type should raise ValueError."""
        f = self._make_upload(content_type="image/bmp")
        with pytest.raises(ValueError, match="[Mm]ime|[Tt]ype|[Uu]nsupported"):
            validate_file(f)

    def test_invalid_mime_type_text(self) -> None:
        """text/plain should raise ValueError."""
        f = self._make_upload(content_type="text/plain")
        with pytest.raises(ValueError, match="[Mm]ime|[Tt]ype|[Uu]nsupported"):
            validate_file(f)


# ── group_files_by_person ─────────────────────────────────


class TestGroupFilesByPerson:
    """Tests for group_files_by_person(parsed_files) → dict of person→files."""

    def test_single_person_multiple_photos(self) -> None:
        """Two photos for same person should be grouped together."""
        files = [
            ("person1_1.jpg", "person1", 1),
            ("person1_2.jpg", "person1", 2),
        ]
        groups = group_files_by_person(files)
        assert "person1" in groups
        assert len(groups["person1"]) == 2

    def test_multiple_persons(self) -> None:
        """Different persons should get separate groups."""
        files = [
            ("alice_1.jpg", "alice", 1),
            ("bob_1.jpg", "bob", 1),
            ("alice_2.png", "alice", 2),
        ]
        groups = group_files_by_person(files)
        assert len(groups) == 2
        assert len(groups["alice"]) == 2
        assert len(groups["bob"]) == 1

    def test_empty_list(self) -> None:
        """Empty file list returns empty dict."""
        groups = group_files_by_person([])
        assert groups == {}


# ── validate_person_references (FR-008) ──────────────────


class TestValidatePersonReferences:
    """Tests for validate_person_references(scenario_text, person_names) → warnings."""

    def test_all_persons_referenced(self) -> None:
        """No warnings when all persons appear in scenario text."""
        warnings = validate_person_references(
            "Alice walks to the park and meets Bob by the fountain.",
            ["alice", "bob"],
        )
        assert warnings == []

    def test_unreferenced_person(self) -> None:
        """Warning when an uploaded person is not mentioned in the scenario."""
        warnings = validate_person_references(
            "Alice walks to the park and person3 waves.",
            ["alice", "bob"],
        )
        assert len(warnings) >= 1
        # "bob" is uploaded but not mentioned in the scenario
        assert any("bob" in w.lower() for w in warnings)

    def test_case_insensitive_matching(self) -> None:
        """Should match case-insensitively."""
        warnings = validate_person_references(
            "ALICE walks to the park.",
            ["alice"],
        )
        assert warnings == []

    def test_no_persons_referenced(self) -> None:
        """Warning for every uploaded person not found in scenario."""
        warnings = validate_person_references(
            "The sun sets over the mountains.",
            ["alice", "bob"],
        )
        # Should warn that alice and bob are not referenced in scenario
        assert len(warnings) >= 2

    def test_empty_scenario(self) -> None:
        """Empty scenario should warn about all persons."""
        warnings = validate_person_references("", ["alice"])
        assert len(warnings) >= 1

    def test_empty_person_list(self) -> None:
        """No persons uploaded = no warnings."""
        warnings = validate_person_references("Some scenario text.", [])
        assert warnings == []
