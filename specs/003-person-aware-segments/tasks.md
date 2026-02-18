# Tasks: Person-Aware Segment Splitting

**Input**: Design documents from `/specs/003-person-aware-segments/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-changes.md, quickstart.md

**Tests**: Constitution mandates TDD (Red-Green-Refactor). All test tasks MUST be completed before their corresponding implementation tasks. Tests MUST fail before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files or independent test cases, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/` (FastAPI + SQLAlchemy)
- **Tests**: `tests/unit/` (pytest + pytest-asyncio)
- **Specs**: `specs/003-person-aware-segments/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

No setup tasks required. The project already exists with all dependencies installed (`google-generativeai`, `fastapi`, `sqlalchemy`, `pytest`). No new packages or DB migrations are needed (Decision 6: transit data only).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

No foundational tasks required. All needed infrastructure (Person model, moderation service, scenarios API, pipeline service) already exists and is tested (88 tests passing). This feature modifies existing code — no new modules, models, or dependencies.

**Checkpoint**: Foundation ready — user story implementation can begin

---

## Phase 3: User Story 2 — Person Names Passed to Splitting (Priority: P1)

**Goal**: The system provides the list of known person names (from uploaded photos) to the splitting process so the AI can correctly reference them in segment descriptions.

**Independent Test**: Verify that `moderate_and_split()` accepts an optional `person_names` parameter and that the prompt sent to Gemini includes the person names when provided. Verify backward compatibility when `person_names` is omitted.

**Why US2 before US1**: US2 is the input mechanism (getting names INTO the prompt). US1 is the output quality (what the AI PRODUCES). US2 must work before US1 can be tested.

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T001 [P] [US2] Write test `test_backward_compat_no_person_names`: call `moderate_and_split(text)` without `person_names` param, assert approved response with segments, assert `characters` defaults to `{}`, assert each segment has `persons` defaulting to `[]` in tests/unit/test_moderation_service.py (FR-009)
- [x] T002 [P] [US2] Write test `test_person_names_included_in_prompt`: call `moderate_and_split(text, person_names=["alice", "bob"])`, capture the prompt passed to `_call_gemini` via mock, assert prompt contains "alice" and "bob" as known characters in tests/unit/test_moderation_service.py
- [x] T003 [P] [US2] Write test `test_empty_person_names_treated_as_none`: call `moderate_and_split(text, person_names=[])`, assert behavior identical to `person_names=None` (no characters section in prompt, `characters` is `{}`) in tests/unit/test_moderation_service.py

### Implementation for User Story 2

- [x] T004 [US2] Update `moderate_and_split()` signature from `(scenario_text: str)` to `(scenario_text: str, person_names: list[str] | None = None)` in backend/services/moderation_service.py (Decision 5: backward-compatible default)
- [x] T005 [US2] Add conditional CHARACTERS prompt section: when `person_names` is non-empty, append a `CHARACTERS` block listing known person names to the prompt; when `None` or empty, omit it entirely in backend/services/moderation_service.py (FR-001, FR-003)
- [x] T006 [US2] Update `submit_scenario()` to set `load_persons=True`, extract `person_names = [p.name for p in project.persons]`, and pass `person_names` to `moderate_and_split(body.text, person_names=person_names)` in backend/api/scenarios.py (contracts/api-changes.md caller change)

**Checkpoint**: US2 testable — person names reach the Gemini prompt. Run `uv run pytest tests/unit/test_moderation_service.py -x -q`

---

## Phase 4: User Story 1 — Segments Include Person References (Priority: P1)

**Goal**: Each segment's description explicitly names person(s) with distinguishing visual traits so the downstream video model can visually identify which character is which.

**Independent Test**: Submit a scenario mentioning two named persons and verify each returned segment description includes relevant person names with visual traits (e.g., "Alice, a tall woman with curly red hair"). Verify the `characters` manifest maps each person to a trait description.

**Depends on**: Phase 3 (US2) — person names must reach the prompt before the AI can reference them.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T007 [P] [US1] Write test `test_person_aware_descriptions_contain_names`: call `moderate_and_split(text, person_names=["alice", "bob"])` with mock returning person-aware response, assert each segment `description` contains at least one person name from `person_names` in tests/unit/test_moderation_service.py (FR-006)
- [x] T008 [P] [US1] Write test `test_characters_manifest_maps_all_persons`: call `moderate_and_split(text, person_names=["alice", "bob"])` with mock response including `characters` dict, assert `result["characters"]` contains keys for both "alice" and "bob" with non-empty string values in tests/unit/test_moderation_service.py (FR-011, FR-012)
- [x] T009 [P] [US1] Write test `test_single_person_in_every_segment`: call with `person_names=["charlie"]`, mock a multi-segment response where every segment references "charlie", assert all segments contain "charlie" in their descriptions in tests/unit/test_moderation_service.py (SC-005)

### Implementation for User Story 1

- [x] T010 [US1] Rewrite `MODERATION_SPLIT_PROMPT` to include visual trait instructions: instruct the AI to reference persons by their given names (FR-002), invent consistent, distinguishing visual traits (clothing, hair, build) for each person, use the "define first, then reference" pattern (Decision 1) — emit `characters` manifest before `segments` in JSON, use EXACT wording from manifest in descriptions (FR-013), describe relative spatial relationships (FR-006a, FR-006b, FR-006c) in backend/services/moderation_service.py
- [x] T011 [US1] Update the JSON output schema in `MODERATION_SPLIT_PROMPT` to include `characters` dict (`{name: visual_description}`) and `persons` array per segment (`["alice", "bob"]`), with concrete example showing the expected format in backend/services/moderation_service.py (FR-011, FR-004)

**Checkpoint**: US1 testable — segments contain person names with visual traits. Run `uv run pytest tests/unit/test_moderation_service.py -x -q`

---

## Phase 5: User Story 3 — Structured Person Data in Segment Output (Priority: P2)

**Goal**: Each segment includes a machine-readable `persons` array listing which characters appear, and a top-level `characters` manifest maps every person to their visual description. Response parsing validates these fields.

**Independent Test**: Verify `parse_gemini_response()` validates that `characters` is a dict with string keys/values, `persons` per segment is a list of strings, entries are normalized to lowercase, and unknown names are filtered out.

**Depends on**: Phase 3 (US2) — `parse_gemini_response()` signature must accept `person_names` for filtering.

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T012 [P] [US3] Write test `test_parse_validates_characters_manifest`: pass raw JSON with valid `characters` dict → assert parsed; pass raw JSON with `characters` as a list → assert `ValueError` raised; pass raw JSON with non-string values in `characters` → assert `ValueError` raised in tests/unit/test_moderation_service.py (FR-014)
- [x] T013 [P] [US3] Write test `test_parse_validates_persons_array`: pass raw JSON with valid `persons` arrays per segment → assert parsed; pass raw JSON with `persons` as a string → assert `ValueError`; pass raw JSON with non-string entries in `persons` → assert `ValueError` in tests/unit/test_moderation_service.py (FR-008)
- [x] T014 [P] [US3] Write test `test_persons_normalized_to_lowercase`: pass raw JSON with `persons: ["Alice", "BOB"]`, assert parsed result has `persons: ["alice", "bob"]` in tests/unit/test_moderation_service.py (FR-010)
- [x] T015 [P] [US3] Write test `test_unknown_persons_filtered_out`: call `parse_gemini_response(raw, person_names=["alice", "bob"])` with a segment containing `persons: ["alice", "charlie"]`, assert result segment has `persons: ["alice"]` only (unknown "charlie" removed) in tests/unit/test_moderation_service.py (FR-005)
- [x] T016 [P] [US3] Write test `test_characters_defaults_empty_when_no_persons`: call `parse_gemini_response(raw)` without `person_names`, assert `result["characters"]` is `{}` and each segment's `persons` is `[]` in tests/unit/test_moderation_service.py (FR-007)
- [x] T024 [P] [US3] Write test `test_persons_inferred_when_not_named_in_scenario`: call `moderate_and_split(text, person_names=["alice"])` where scenario text uses generic terms ("a person walks") without naming alice, verify the prompt still includes "alice" as a known character so the AI can infer assignment in tests/unit/test_moderation_service.py (Edge Case 2)
- [x] T025 [P] [US3] Write test `test_rejected_scenario_with_person_names`: call `moderate_and_split(text, person_names=["alice", "bob"])` with mock returning rejected response, assert `characters` is `{}`, `segments` is `[]`, rejection behavior preserved — person_names does not interfere with moderation in tests/unit/test_moderation_service.py (FR-009, Edge Case 5)

### Implementation for User Story 3

- [x] T017 [US3] Update `parse_gemini_response()` signature to accept `person_names: list[str] | None = None` and add `characters` manifest validation: when `person_names` provided, assert `characters` exists and is `dict[str, str]`; when not provided, default to `{}` in backend/services/moderation_service.py (FR-014, FR-012)
- [x] T018 [US3] Add `persons` array validation per segment in `parse_gemini_response()`: assert `persons` is `list[str]`, normalize entries to lowercase (FR-010), filter against `person_names` to remove unknown names (FR-005), default to `[]` when `person_names` not provided (FR-007) in backend/services/moderation_service.py
- [x] T019 [US3] Update `moderate_and_split()` to pass `person_names` through to `parse_gemini_response(raw_response, person_names=person_names)` in backend/services/moderation_service.py

**Checkpoint**: US3 testable — structured person data validated and normalized. Run `uv run pytest tests/unit/test_moderation_service.py -x -q`

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and final validation

- [x] T020 [P] Simplify `initial_prompt` in `run_pipeline()`: remove manual `person_str` concatenation (`person_str = ", ".join(person_names)...`), use `first_segment['description']` directly since descriptions now embed visual traits (contracts/api-changes.md pipeline change) in backend/services/pipeline_service.py
- [x] T021 [P] Add `response_mime_type="application/json"` to `_call_gemini()` via `GenerationConfig` for reliable JSON output without code fences (Decision 2), keep existing code-fence stripping in `parse_gemini_response()` as defense-in-depth in backend/services/moderation_service.py
- [x] T022 Run full test suite `uv run pytest -x -q` and verify all tests pass (existing 88 + new person-aware tests)
- [x] T023 Run quickstart.md manual verification: test `moderate_and_split()` with person_names in Python REPL, verify characters manifest, verify backward compat without person_names per specs/003-person-aware-segments/quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Skipped — existing project
- **Foundational (Phase 2)**: Skipped — no blocking infrastructure needed
- **US2 (Phase 3)**: No dependencies — can start immediately. BLOCKS US1 and US3.
- **US1 (Phase 4)**: Depends on US2 (Phase 3) — person names must reach the prompt first
- **US3 (Phase 5)**: Depends on US2 (Phase 3) — `parse_gemini_response()` needs `person_names` param. Can run in parallel with US1 (different concerns: prompt content vs response parsing).
- **Polish (Phase 6)**: Depends on US1 + US3 completion

### User Story Dependencies

- **US2 (P1)**: Start immediately — function signature + prompt injection + caller update
- **US1 (P1)**: Start after US2 — prompt content for visual traits (extends prompt from US2)
- **US3 (P2)**: Start after US2 — response parsing validation (can run in parallel with US1)
- **US1 and US3 can proceed in parallel** after US2 is complete (US1 modifies prompt content, US3 modifies parsing logic — different code sections)

### Within Each User Story

1. Tests MUST be written and MUST FAIL before implementation
2. Implementation follows test failures
3. All tests for the story must PASS after implementation
4. Story checkpoint validates independent functionality

### Parallel Opportunities

- **Phase 3 (US2)**: T001, T002, T003 can run in parallel (independent test cases)
- **Phase 4 (US1)**: T007, T008, T009 can run in parallel (independent test cases)
- **Phase 5 (US3)**: T012–T016 can run in parallel (independent test cases)
- **Phase 4 & 5**: US1 implementation (T010–T011) and US3 implementation (T017–T019) can run in parallel (prompt changes vs parsing changes)
- **Phase 6**: T020 and T021 can run in parallel (different files)

---

## Parallel Example: User Story 2

```bash
# Launch all US2 tests together (all write to different test functions):
Task: T001 "Test backward compat (no person_names)" in tests/unit/test_moderation_service.py
Task: T002 "Test person_names included in prompt" in tests/unit/test_moderation_service.py
Task: T003 "Test empty person_names treated as None" in tests/unit/test_moderation_service.py

# Then implement sequentially:
Task: T004 "Update moderate_and_split() signature" in backend/services/moderation_service.py
Task: T005 "Add conditional CHARACTERS prompt section" in backend/services/moderation_service.py
Task: T006 "Update submit_scenario() caller" in backend/api/scenarios.py
```

## Parallel Example: US1 + US3 After US2

```bash
# After US2 is complete, US1 and US3 can proceed in parallel:

# Developer A — US1 (prompt content):
Task: T007-T009 "US1 tests" in tests/unit/test_moderation_service.py
Task: T010-T011 "Prompt rewrite" in backend/services/moderation_service.py

# Developer B — US3 (response parsing):
Task: T012-T016, T024-T025 "US3 tests" in tests/unit/test_moderation_service.py
Task: T017-T019 "Parsing validation" in backend/services/moderation_service.py
```

---

## Implementation Strategy

### MVP First (User Story 2 Only)

1. Complete Phase 3: US2 — person names reach the prompt
2. **STOP and VALIDATE**: Test that person names appear in the Gemini prompt
3. The AI will naturally start including person names in descriptions even without explicit trait instructions
4. This alone provides value — segments will reference persons by name

### Incremental Delivery

1. Complete US2 → Person names flow into prompt → Test independently → **MVP!**
2. Add US1 → Rich visual traits in descriptions → Test independently
3. Add US3 → Structured validation + normalization → Test independently
4. Polish → Pipeline simplification + reliability improvements
5. Each story adds value without breaking previous stories

### Key Technical Decisions (from research.md)

| # | Decision | Impact |
|---|----------|--------|
| 1 | "Define first, then reference" prompt pattern | `characters` manifest emitted before `segments` in JSON |
| 2 | `response_mime_type="application/json"` | Reliable JSON output, code-fence stripping as fallback |
| 3 | Flash adequate for ≤5 chars / ≤15 segments | No model upgrade needed |
| 4 | Accept paraphrasing risk, mitigate with prompts | No retry logic needed initially |
| 5 | Backward-compatible `person_names=None` default | Existing callers unaffected |
| 6 | No DB schema changes (transit data only) | No migrations, `persons` field is in-memory only |

---

## Notes

- [P] tasks = different files or independent test functions, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Constitution mandates TDD: verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Primary file: `backend/services/moderation_service.py` (prompt, signature, parsing)
- Secondary files: `backend/api/scenarios.py` (caller), `backend/services/pipeline_service.py` (consumer)
- Test file: `tests/unit/test_moderation_service.py` (all new tests)
- Total tasks: 25 (3 phases of tests + implementation + polish)
- Estimated new test count: 13 new tests (T001–T003, T007–T009, T012–T016, T024–T025)
