# Feature Specification: Person-Aware Segment Splitting

**Feature Branch**: `003-person-aware-segments`  
**Created**: 2025-07-15  
**Status**: Draft  
**Input**: User description: "Update MODERATION_SPLIT_PROMPT so each segment contains person information for video generation"

## Clarifications

### Session 2026-02-18

- Q: Where should visual descriptions of persons come from for the video model to visually identify them? → A: The splitting AI invents consistent visual traits for each person and uses them across all segments.
- Q: How should segments describe person positions/locations in the frame? → A: Describe relative spatial relationships between persons (e.g., "Alice facing Bob," "Alice lifts Bob") without specifying exact frame positions.
- Q: Should segments include a per-person action breakdown or just a unified scene description? → A: A single unified scene description that weaves person names, traits, and actions together in natural prose.
- Q: Should the visual traits invented for persons be returned as structured data alongside segments? → A: Yes, include a top-level `characters` manifest mapping each person name to their visual description, so the pipeline can reuse it for consistent image generation prompts.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Segments Include Person References (Priority: P1)

A user uploads photos of two people (e.g., "alice" and "bob") and writes a scenario describing a conversation between them. When the system moderates and splits the scenario into video segments, each segment's description explicitly states which person(s) appear in that segment and what they are doing. This allows the downstream video generation pipeline to know which character(s) to render in each clip.

**Why this priority**: Without person information in segments, the video generation pipeline cannot correctly associate characters with scenes. This is the core value of the feature — every other improvement depends on segments containing person references.

**Independent Test**: Can be tested by submitting a scenario mentioning two named persons and verifying that each returned segment description includes the relevant person name(s), their distinguishing visual traits, and their actions in that segment.

**Acceptance Scenarios**:

1. **Given** a project with persons "alice" and "bob" and a scenario describing them talking, **When** the scenario is moderated and split, **Then** each segment description explicitly names which person(s) appear along with distinguishing visual traits (e.g., "Alice, a tall woman with curly red hair, stands at the doorway greeting Bob, a shorter man with glasses and a blue jacket"), and the response includes a `characters` manifest mapping each name to their visual traits.
2. **Given** a project with persons "alice" and "bob" and a scenario where only alice appears in the first half and bob joins later, **When** the scenario is split, **Then** early segments reference only "alice" and later segments reference both "alice" and "bob".
3. **Given** a project with a single person "charlie", **When** the scenario is split, **Then** every segment references "charlie" by name.

---

### User Story 2 - Person Names Passed to Splitting (Priority: P1)

The system provides the list of known person names (derived from uploaded photo filenames) to the splitting process so the AI can correctly reference them. The person names are injected into the moderation/splitting prompt alongside the scenario text.

**Why this priority**: The splitting AI cannot reference persons by name if it doesn't know which names exist in the project. This is a prerequisite for User Story 1.

**Independent Test**: Can be tested by verifying that the prompt sent to the AI model includes the list of person names extracted from uploaded photos.

**Acceptance Scenarios**:

1. **Given** a project with persons "alice" and "bob", **When** the moderation/splitting prompt is constructed, **Then** the prompt includes "alice" and "bob" as known characters.
2. **Given** a project with no persons (no photos uploaded yet), **When** the moderation/splitting prompt is constructed, **Then** the prompt handles the absence gracefully and does not include an empty person list instruction.

---

### User Story 3 - Structured Person Data in Segment Output (Priority: P2)

Each segment in the moderation/splitting response includes a structured field listing which persons appear in that segment, in addition to the descriptive text. This provides a machine-readable mapping of persons to segments for the pipeline to consume.

**Why this priority**: While the descriptive text (P1) is essential for visual generation, a structured person list per segment enables the pipeline to programmatically select the correct reference photos for each clip without parsing natural language.

**Independent Test**: Can be tested by verifying the response for a multi-person scenario includes a persons array per segment, and each array contains only the persons who appear in that segment.

**Acceptance Scenarios**:

1. **Given** an approved scenario with persons "alice" and "bob", **When** the response is parsed, **Then** each segment contains a `persons` field listing the names of characters in that segment.
2. **Given** a segment where only "alice" appears, **When** the response is parsed, **Then** that segment's `persons` field contains only `["alice"]`.
3. **Given** a segment where both characters interact, **When** the response is parsed, **Then** that segment's `persons` field contains `["alice", "bob"]`.

---

### Edge Cases

- What happens when a scenario mentions a name that does not match any uploaded person? The segment should still describe the scene but the `persons` field should only include names from the known person list.
- What happens when the scenario does not mention any person by name but persons exist in the project? The AI should infer character assignments from context or default to including all persons in segments where characters are implied.
- What happens when there is only one person in the project? All segments featuring a character should reference that single person.
- What happens when a person name appears differently in the scenario (e.g., "Alice" vs "alice")? The system should perform case-insensitive matching and use the canonical (lowercase) name in the `persons` field.
- What happens when the scenario is rejected (content moderation failure)? The segments array is empty and the `persons` field is not relevant — existing rejection behavior is preserved.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The moderation/splitting process MUST accept a list of person names alongside the scenario text.
- **FR-002**: The moderation/splitting prompt MUST instruct the AI to reference persons by their given names in each segment description.
- **FR-003**: The moderation/splitting prompt MUST provide the known person names to the AI so it can use them accurately.
- **FR-004**: Each segment in the approved response MUST include a `persons` field containing the list of person names who appear in that segment.
- **FR-005**: The `persons` field MUST only contain names from the known person list provided to the prompt (no invented names).
- **FR-006**: The segment description text MUST explicitly name the person(s) performing actions in that segment AND include distinguishing visual traits (e.g., "Alice, a tall woman with curly red hair, walks toward the camera" rather than "A person walks toward the camera").
- **FR-006a**: The splitting AI MUST invent consistent, distinguishing visual traits (clothing, hair, build, etc.) for each person and reuse the same traits across all segments so the video model can visually identify which character is which.
- **FR-006b**: Visual traits MUST be introduced in the first segment a person appears in and referenced consistently in subsequent segments.
- **FR-006c**: Segment descriptions MUST use relative spatial relationships between persons (e.g., "Alice stands facing Bob," "Alice lifts Bob from behind") rather than explicit frame positions (e.g., "left of frame"). This gives the video model enough context to assign actions to the correct person without over-constraining composition.
- **FR-011**: The approved response MUST include a top-level `characters` field — a mapping of each person name to a short visual description (e.g., `{"alice": "tall woman with curly red hair and a green dress", "bob": "shorter man with glasses and a blue jacket"}`).
- **FR-012**: The `characters` manifest MUST contain an entry for every person name provided in the prompt input.
- **FR-013**: The visual traits in the `characters` manifest MUST match the traits used in segment descriptions — no contradictions between the manifest and the segment text.
- **FR-014**: The response parsing MUST validate that the `characters` field exists (when persons are provided), is a dictionary, and contains only string keys and string values.
- **FR-007**: The system MUST handle projects with zero persons gracefully — segments should describe scenes without character names, and the `persons` field should be an empty array.
- **FR-008**: The response parsing MUST validate that the `persons` field exists in each segment and contains only strings.
- **FR-009**: The system MUST preserve all existing moderation behavior (content policy checks, rejection reasons, maximum 15 segments).
- **FR-010**: Person name matching in the AI output MUST be case-insensitive and normalized to lowercase in the `persons` field.

### Key Entities

- **Person**: A named character in a project, derived from uploaded photo filenames. Has a name (string, unique per project) and associated reference photos.
- **Segment**: A discrete scene description for video generation. Currently contains `sequence_number` and `description`. This feature adds a `persons` field (list of person name strings) identifying which characters appear in the segment.
- **Characters Manifest**: A top-level response field mapping each person name to a short visual trait description. Used by the pipeline to maintain consistent character appearance across all generation prompts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of segments in an approved response for a multi-person scenario include a non-empty `persons` field listing the characters in that segment.
- **SC-002**: 100% of segment descriptions for approved scenarios mention at least one person by name when persons are provided.
- **SC-003**: The video generation pipeline can determine which person's reference photos to use for each segment without any natural language parsing — using the structured `persons` field alone.
- **SC-006**: The `characters` manifest provides a single source of truth for visual traits, and segment descriptions use traits consistent with this manifest.
- **SC-004**: All existing moderation tests continue to pass — no regression in content policy enforcement or segment splitting behavior.
- **SC-005**: Scenarios with a single person result in that person being referenced in every segment where a character appears.

## Assumptions

- Person names are always lowercase strings derived from photo filenames (e.g., "alice", "bob") — this is enforced by the existing upload filename parsing.
- The AI model can reliably follow instructions to include person names in segment descriptions and produce a structured `persons` array per segment.
- The video generation pipeline already receives person names — this feature ensures that information also flows into the moderation/splitting step.
- The maximum number of persons per project is small enough (typically 1–5) that listing all names in the prompt does not significantly impact processing.
