# Research: Code Walkthrough Documentation

**Feature**: 004-code-walkthrough-docs  
**Date**: 2026-02-28

## Research Task 1: Mermaid Diagram Syntax & Compatibility

### Decision
Use the following Mermaid diagram types, all confirmed to render on GitHub and VS Code:

| Diagram Type | Mermaid Keyword | Orientation |
|---|---|---|
| ER diagram | `erDiagram` | auto |
| State machine | `stateDiagram-v2` | auto |
| Auth sequences | `sequenceDiagram` | left→right |
| Pipeline flowchart | `flowchart TD` | top→down |
| Upload flowchart | `flowchart TD` | top→down |
| Architecture layers | `graph TD` with subgraphs | top→down |
| Moderation sequence | `sequenceDiagram` | left→right |

### Rationale
- All keywords render correctly in GitHub Markdown and VS Code Mermaid Preview
- `flowchart` (not `graph`) is preferred for newer node shapes like `([...])` for start/end
- `stateDiagram-v2` (not v1) supports composite states for nested generation loop
- C4 diagrams (`C4Context`) are NOT rendered by GitHub — avoided
- `block-beta` is too new with limited support — avoided

### Alternatives Considered
- **PlantUML**: Not text-native to GitHub, requires external rendering
- **draw.io/Excalidraw**: Binary or JSON files, not version-controllable as text
- **ASCII art**: Limited expressiveness for complex flows

### Key Syntax Notes
- ER: Use `PK`, `FK`, `UK` keywords after attribute names; use quotes for constraints/comments
- State: `[*]` for start/end pseudo-states; `state X { }` for composite states; `<<choice>>` for decision points
- Sequence: `rect rgb(...)` for grouped sections; `alt`/`opt` for conditionals; `-->>` for responses
- Flowchart: `subgraph` for loops; diamond `{ }` for decisions; `([text])` for start/end; `<br/>` for line breaks

---

## Research Task 2: Exact Enum Values & State Transitions

### Decision
Document all enum values exactly as defined in the codebase. Mark unimplemented transitions clearly.

### Findings

**Enums** (all verified against source):

| Enum | File | Values |
|------|------|--------|
| `VideoStyle` | `backend/models/project.py` L25–28 | `animation`, `movie_like` |
| `ProjectStatus` | `backend/models/project.py` L31–44 | `draft`, `submitted`, `moderating`, `splitting`, `reviewing`, `generating`, `concatenating`, `completed`, `rejected`, `failed` |
| `ModerationStatus` | `backend/models/scenario.py` L25–29 | `pending`, `approved`, `rejected` |
| `GenerationStatus` | `backend/models/scenario.py` L32–37 | `pending`, `generating`, `completed`, `failed` |
| `ClipStatus` | `backend/models/video.py` L25–30 | `pending`, `generating`, `completed`, `failed` |

**Implemented status transitions** (only these exist in code):

| Transition | Trigger | File:Line |
|---|---|---|
| (new) → `draft` | Project created (default) | model default |
| any → `GENERATING` | `POST /api/projects/{id}/generate` | `generation.py` L77 |
| (new Scenario) → `APPROVED` or `REJECTED` | `PUT /api/projects/{id}/scenario` → Gemini result | `scenarios.py` L55–61 |

**NOT implemented (placeholder)**:
- `SUBMITTED`, `MODERATING`, `SPLITTING`, `REVIEWING` — defined but never assigned
- `CONCATENATING`, `COMPLETED`, `FAILED` — defined but no transition logic exists
- Pipeline completion does not update project status

### Rationale
The state diagram in the walkthrough will show the **intended** full lifecycle as designed by the enum, but clearly mark which transitions are actually implemented vs. scaffolded.

---

## Research Task 3: Placeholder & Incomplete Features

### Decision
Create a dedicated "Implementation Status" callout in the walkthrough marking all known placeholders.

### Findings

| Feature | Status | Detail |
|---|---|---|
| `launch_pipeline()` | **Placeholder** (`pass`) | `generation.py` L22–35 — body is literally `pass`. Never calls `pipeline_service.run_pipeline()`. Docstring says "will be wired to BackgroundTasks or a task queue." |
| Video concatenation | **Not implemented** | No concat service exists. `FinalVideo` model and `CONCATENATING` status are scaffolded. ffmpeg is only used for last-frame extraction. |
| `FinalVideoResponse` in project detail | **Stub** | `schemas/project.py` L48: `final_video: dict \| None = None  # Will be FinalVideoResponse in Phase 6` |
| Most `ProjectStatus` transitions | **Not wired** | Only `→ GENERATING` is implemented. All other transitions (`SUBMITTED`, `MODERATING`, etc.) exist as enum values but are never assigned. |
| Contract tests | **Empty directory** | `tests/contract/` exists but contains no test files |

### Rationale
Documenting these gaps honestly helps reviewers understand the current state and prevents false assumptions about completeness.

---

## Research Task 4: API Route Structure Verification

### Decision
Document all routes with exact prefixes as defined in router instantiation.

### Findings

| Router File | `prefix=` | `tags=` | Endpoints |
|---|---|---|---|
| `health.py` | *(none)* | `["Health"]` | `GET /health` |
| `auth.py` | `"/api/auth"` | `["Auth"]` | `POST /register`, `POST /login`, `GET /me`, `GET /google`, `GET /google/callback` |
| `projects.py` | `"/api/projects"` | `["Projects"]` | `POST /`, `GET /`, `GET /{id}`, `DELETE /{id}`, `POST /{id}/photos`, `GET /{id}/photos`, `DELETE /{id}/photos/{photo_id}` |
| `scenarios.py` | `"/api/projects"` | `["Scenarios"]` | `PUT /{id}/scenario`, `GET /{id}/scenario` |
| `generation.py` | `"/api/projects"` | `["Generation"]` | `POST /{id}/generate`, `GET /{id}/status` |
| `pages.py` | *(none)* | `["Pages"]` | `GET /`, `/login`, `/register`, `/logout`, `/dashboard`, `/new-project`, `/projects/{id}` |

**Note**: `scenarios.py` and `generation.py` share the `/api/projects` prefix with `projects.py`. This is intentional — they extend the projects resource with sub-resource endpoints.

---

## Research Task 5: Person-Aware Moderation Prompt Structure

### Decision
Document the dual-section prompt structure with character manifest.

### Findings

The moderation prompt in `moderation_service.py` has two parts:

1. **Base prompt** (`MODERATION_SPLIT_PROMPT`, L23–56): Content moderation rules + scenario splitting instructions. Always included.
2. **Characters section** (`_CHARACTERS_SECTION`, L59–90): Person-aware tracking. Only appended when `person_names` is non-empty.

**Character manifest rules from the prompt**:
- Reference each character by name in every segment they appear
- Invent a short distinguishing visual description (2–3 traits) per character
- Use the exact same visual description each time (no paraphrasing)
- Describe spatial relationships between characters
- `"characters"` field maps `name → visual_description`
- Each segment's `"persons"` array lists only names present in that segment

**Validation in `parse_gemini_response()`** (L116–192):
- `characters` must be `dict[str, str]`
- Per-segment `persons` must be `list[str]`
- Person names normalized to lowercase
- Unknown names (not in project's person list) are filtered out

### Rationale
This is a well-implemented feature worth highlighting in the walkthrough as it shows sophisticated AI prompt engineering with validation guardrails.

---

## Research Task 6: Video Generation Pipeline Details

### Decision
Document both the implemented pipeline logic and the unimplemented wiring.

### Findings

**Implemented** (`pipeline_service.py`):
- `run_pipeline(segments, style, output_dir, persons)` — orchestrates full pipeline
- Step 1: Generate initial image from first segment description + style → `image_gen_service.generate_initial_image()`
- Step 2: For each segment: generate video clip → extract last frame → use as next input
- Retry: `MAX_RETRIES = 1` — failed clips retried once
- Returns list of `{sequence_number, video_path, last_frame_path}`

**Implemented** (`image_gen_service.py`):
- `generate_initial_image()` — calls fal.ai Qwen Image model
- Style prefix: "cartoon, stylized animation style" or "realistic, cinematic movie style"
- Downloads result via httpx and saves locally

**Implemented** (`video_gen_service.py`):
- `generate_video_clip()` — calls fal.ai LTX Video 13B, 854×480, 121 frames (~5s at 24fps), no audio
- `extract_last_frame()` — ffmpeg subprocess: `-sseof -0.1 -vframes 1`

**NOT implemented**:
- Background task wiring (`launch_pipeline` is `pass`)
- Video concatenation service
- FinalVideo record creation
- Project status progression through the pipeline

### Rationale
The pipeline logic is complete as a synchronous function but lacks the async wiring and post-processing. The walkthrough should show the intended flow while marking the gaps.

---

## Research Task 7: Constitution-Mandated Features — Email Verification, Terms of Use, Ad Zones

*Added during `/speckit.analyze` remediation (C2, C3)*

### Decision
Document these as **scaffolded-only** features in the walkthrough's Implementation Status section (Section 15).

### Findings

**Email Verification**:
- `User.email_verified` column exists (`backend/models/user.py` L40) as `bool`, default `False`
- Google OAuth users get `email_verified=True` automatically (`auth_service.py` L121, L130)
- `UserResponse` schema exposes `email_verified` (`schemas/auth.py` L38)
- **No send-verification endpoint**, no verification token generation, no verification email sending
- Constitution mandates: "Email verification is required for email/password registrations" — **NOT enforced**
- Status: **Scaffolded column only** — email registration works without verification

**Terms of Use Acceptance**:
- `User.terms_accepted_at` column exists (`backend/models/user.py` L45) as `datetime | None`
- `UserResponse` schema exposes `terms_accepted_at` (`schemas/auth.py` L39)
- **No accept-terms endpoint**, no middleware gate blocking access, no terms presentation page
- Constitution mandates: "Terms of Use must be presented and accepted before any platform features are accessible" — **NOT enforced**
- Status: **Scaffolded column only** — all features accessible without terms acceptance

**Ad Integration**:
- `base.html` L48 contains `<div class="ad-zone ad-zone--footer">` — a single footer ad zone
- Constitution specifies three zones: sidebar, banner, interstitial
- **Only footer zone exists**; no sidebar, banner, or interstitial zones
- No JS ad loader or graceful fallback handling
- Status: **Partially scaffolded** — single placeholder div, not connected to an ad provider

### Rationale
These three constitution-mandated features have DB/template scaffolding but no functional implementation. They must be included in Section 15 (Implementation Status) alongside existing placeholders like `launch_pipeline()` and missing concatenation service. This ensures the walkthrough accurately reflects the gap between constitution requirements and current implementation.
