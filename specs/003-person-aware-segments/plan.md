# Implementation Plan: Person-Aware Segment Splitting

**Branch**: `003-person-aware-segments` | **Date**: 2026-02-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-person-aware-segments/spec.md`

## Summary

Update the moderation/splitting system so each video segment includes person identification information — names, AI-invented visual traits, a structured `persons` list per segment, and a top-level `characters` manifest. This enables the downstream image-to-video pipeline to visually distinguish and correctly render each character across all generated clips.

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI, google-generativeai (Gemini 2.5 Flash), SQLAlchemy 2.0 async, Pydantic v2
**Storage**: SQLite (aiosqlite) for dev; async SQLAlchemy ORM models (Scenario, Segment, Person)
**Testing**: pytest + pytest-asyncio + httpx; 88 tests currently passing; Constitution mandates TDD (Red-Green-Refactor)
**Target Platform**: Linux/Windows server (uvicorn)
**Project Type**: Web application (FastAPI backend + Jinja2 templates)
**Performance Goals**: Single Gemini API call per scenario (no additional calls)
**Constraints**: Must preserve existing moderation behavior; max 15 segments; person names are lowercase strings from uploaded photo filenames
**Scale/Scope**: 1–5 persons per project typical; prompt additions are small (~50 tokens for person list)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Privacy-First | ✅ PASS | No change to data isolation — person names already isolated per project |
| II. Content Safety | ✅ PASS | Content moderation preserved (FR-009); same CONTENT POLICY block retained |
| III. Security by Default | ✅ PASS | No new secrets/credentials; no new endpoints; existing auth preserved |
| IV. Responsive & Accessible | ✅ PASS | Backend-only change; no UI impact |
| V. Test-First (NON-NEGOTIABLE) | ✅ PASS | Tests must be written first for new `person_names` param, `characters` manifest, `persons` field parsing, and updated prompt format |
| VI. Deployment Readiness | ✅ PASS | No new dependencies; no schema migration needed (persons field is in AI response JSON, not DB column) |
| VII. Professional Standards | ✅ PASS | Modular change to existing service; clean separation of concerns |
| YAGNI | ✅ PASS | All additions directly serve the spec requirements; no speculative features |

**Gate result: PASS** — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/003-person-aware-segments/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
backend/
├── services/
│   ├── moderation_service.py    # PRIMARY: Update MODERATION_SPLIT_PROMPT, moderate_and_split(), parse_gemini_response()
│   └── pipeline_service.py      # SECONDARY: Use characters manifest for initial_prompt
├── api/
│   └── scenarios.py             # SECONDARY: Pass person_names to moderate_and_split()
├── models/
│   └── scenario.py              # OPTIONAL: Add persons_json column to Segment if needed
└── schemas/
    └── scenario.py              # SECONDARY: Add persons field to SegmentResponse

tests/
├── unit/
│   └── test_moderation_service.py  # PRIMARY: Tests for person-aware splitting
└── integration/
    └── test_scenario_api.py        # SECONDARY: Integration tests for person-aware flow
```

**Structure Decision**: Existing web application layout; changes touch 3–5 existing files with no new modules.

## Complexity Tracking

> No constitution violations — table not applicable.
