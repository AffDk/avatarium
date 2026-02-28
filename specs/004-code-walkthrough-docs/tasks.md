# Tasks: Code Walkthrough Documentation with Mermaid Visualizations

**Input**: Design documents from `/specs/004-code-walkthrough-docs/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Tests**: Not applicable — this is a documentation-only feature. Validation is manual (verify diagrams match source code, Mermaid syntax renders correctly).

**Organization**: Tasks are grouped by user story to enable independent writing and review of each section.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different sections, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US6)
- All tasks produce content in `specs/004-code-walkthrough-docs/walkthrough.md`

---

## Phase 1: Setup (Document Scaffold)

**Purpose**: Create the walkthrough document with table of contents and section stubs

- [ ] T001 Create walkthrough.md with document header, "Last verified" commit reference, and introduction in specs/004-code-walkthrough-docs/walkthrough.md
- [ ] T002 Add table of contents with anchor links to all 16 sections per FR-019 in specs/004-code-walkthrough-docs/walkthrough.md
- [ ] T003 Add empty section headings (H2) for all 16 sections as stubs in specs/004-code-walkthrough-docs/walkthrough.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Write the cross-cutting infrastructure sections that other user story sections reference

**⚠️ CRITICAL**: These sections establish terminology and concepts referenced by all user story sections

- [ ] T004 [US1] Write Section 2: Configuration System — describe Pydantic Settings, env var groups (App, DB, fal.ai, Gemini, OAuth, JWT, Rate Limit), singleton pattern, `is_development`/`is_production` properties per FR-011. Reference: backend/config.py
- [ ] T005 [US1] Write Section 3: Database Layer — describe async engine creation, `async_session_factory` with `expire_on_commit=False`, `get_db()` dependency (yield session, auto-commit/rollback), `create_all()` for dev, `dispose_engine()` cleanup per FR-012. Reference: backend/database.py
- [ ] T006 [US1] Write Section 11: Middleware — describe SlowAPI `Limiter` with `get_remote_address` key function, default rate from settings, `SessionMiddleware` for OAuth state, attachment to app via `app.state.limiter` per FR-013. Reference: backend/middleware/rate_limit.py, backend/main.py
- [ ] T007 [US1] Write Section 12: Logging — describe `setup_logging()`, per-session file under `logs/session_YYYYMMDD_HHMMSS.log`, DEBUG file handler, INFO console handler, format `timestamp | LEVEL | logger_name | message`, idempotent handler clearing per FR-014. Reference: backend/logging_config.py

**Checkpoint**: Infrastructure sections complete — user story sections can now reference them

---

## Phase 3: User Story 1 — Architecture Overview (Priority: P1) 🎯 MVP

**Goal**: Provide a top-down view of the entire platform with a layered architecture Mermaid diagram

**Independent Test**: Verify the architecture diagram shows all layers (client, static, page routes, API routes, services, models, DB, external APIs) and every major module is represented

### Implementation

- [ ] T008 [US1] Write Section 1 narrative: describe each architectural layer — Browser/Client, Static Assets (CSS/JS), Jinja2 Templates, Page Routes (pages.py), API Routes (auth, projects, scenarios, generation, health), Service Layer (auth, upload, moderation, pipeline, image_gen, video_gen), Data Layer (SQLAlchemy models + schemas), External APIs (fal.ai, Gemini, Google OAuth). Reference: backend/main.py for app factory and router wiring
- [ ] T009 [US1] Create Mermaid `graph TD` architecture diagram with subgraphs for each layer per FR-001 — use research.md syntax patterns: `subgraph` for layers, cylinder `[( )]` for database, fan-out `&` syntax, emoji labels. Include all 6 API routers, all 6 services, models block, and 3 external APIs. Add to Section 1 of specs/004-code-walkthrough-docs/walkthrough.md

**Checkpoint**: US1 complete — reviewer can see the full system architecture at a glance

---

## Phase 4: User Story 2 — Data Model & Entity Relationships (Priority: P1)

**Goal**: Document all 8 database tables, their fields, relationships, and all enum types with an ER diagram

**Independent Test**: Compare every table, column, FK, and enum value against backend/models/ source files

### Implementation

- [ ] T010 [US2] Write Section 3 ER diagram: create Mermaid `erDiagram` covering all 8 tables (users, projects, persons, photos, scenarios, segments, video_clips, final_videos) with PK/FK/UK markers, type annotations, constraint comments, and correct cardinality lines per FR-002. Use research.md verified syntax patterns. Add to Section 3 of specs/004-code-walkthrough-docs/walkthrough.md. **Depends on T005** (Section 3 narrative must exist before adding ER diagram).
- [ ] T011 [P] [US2] Write Section 4 field descriptions: for each of the 8 tables, write a subsection with a field table (Column, Type, Constraints, Notes) covering every column. Reference: backend/models/user.py, backend/models/project.py, backend/models/scenario.py, backend/models/video.py
- [ ] T012 [P] [US2] Write Section 4 enum tables per FR-003: create tables for VideoStyle (2 values), ProjectStatus (10 values), ModerationStatus (3 values), GenerationStatus (4 values), ClipStatus (4 values) — using exact values from research.md. Mark which values are actually used in code vs. scaffolded-only per research Task 2 findings
- [ ] T013 [US2] Write Section 4 relationships narrative: describe all foreign key relationships with cascade rules, unique constraints (project→scenario 1:1, project→final_video 1:1), and the selectin eager loading pattern on Project→persons. Reference: backend/models/__init__.py for model registry

**Checkpoint**: US2 complete — reviewer understands all data structures without reading model files

---

## Phase 5: User Story 6 — Video Generation Pipeline (Priority: P1)

**Goal**: Document the iterative video generation pipeline with a flowchart showing the loop, retry logic, and external API calls

**Independent Test**: Walk through the flowchart step-by-step against pipeline_service.py, image_gen_service.py, and video_gen_service.py

### Implementation

- [ ] T014 [US6] Write Section 8 narrative: describe the full pipeline flow — initial image generation via fal.ai Qwen (with style prefix: "cartoon, stylized animation style" or "realistic, cinematic movie style"), iterative per-segment video clip generation via fal.ai LTX Video 13B (854×480, 121 frames, ~5s at 24fps, no audio), last-frame extraction via FFmpeg (`-sseof -0.1 -vframes 1`), chaining mechanism (last frame becomes next input), retry logic (MAX_RETRIES = 1), and httpx download pattern. Mark `launch_pipeline()` as placeholder per FR-018. Reference: backend/services/pipeline_service.py, backend/services/image_gen_service.py, backend/services/video_gen_service.py
- [ ] T015 [US6] Create Mermaid `flowchart TD` pipeline diagram per FR-008 — show Start → Generate Initial Image (fal.ai Qwen) → Set current_image → Loop decision "More segments?" → subgraph "For Each Segment" containing: Generate Video Clip (fal.ai LTX Video) → Success? decision → Extract Last Frame (FFmpeg) → Update current_image → Store Result → back to loop; failure path: retry_count < 1? → retry or Pipeline Failed. Use research.md flowchart patterns. Add to Section 8 of specs/004-code-walkthrough-docs/walkthrough.md

**Checkpoint**: US6 complete — reviewer understands the core video generation flow

---

## Phase 6: User Story 9 — Project Status State Machine (Priority: P2)

**Goal**: Visualize all project statuses and transitions in a state diagram, clearly marking implemented vs. scaffolded transitions

**Independent Test**: Compare every state and transition against ProjectStatus enum and actual `.status =` assignments in code

### Implementation

- [ ] T016 [US9] Create Mermaid `stateDiagram-v2` for ProjectStatus lifecycle per FR-004 — show all 10 states: [*]→DRAFT→SUBMITTED→MODERATING→SPLITTING→REVIEWING→GENERATING→CONCATENATING→COMPLETED, with branches to REJECTED (from MODERATING) and FAILED (from GENERATING, CONCATENATING). Use `<<choice>>` for moderation decision. Add composite state for GENERATING showing clip sub-states. Use notes to mark which transitions are implemented (only DRAFT default, any→GENERATING) vs. scaffolded. Add to Section 4 of specs/004-code-walkthrough-docs/walkthrough.md
- [ ] T017 [US9] Write Section 4 state machine narrative: describe intended lifecycle, explain each state's meaning, list which API endpoint triggers each transition, and add a callout box marking that only `→ GENERATING` transition is currently wired per research Task 2 findings

**Checkpoint**: US9 complete — reviewer can verify project status management correctness

---

## Phase 7: User Story 3 — Authentication Flow (Priority: P2)

**Goal**: Document the full auth system with sequence diagrams for email auth and Google OAuth

**Independent Test**: Follow each sequence diagram and verify every step matches backend/api/auth.py and backend/services/auth_service.py

### Implementation

- [ ] T018 [US3] Write Section 5 narrative: describe email/password registration (bcrypt hashing, email uniqueness check, `email_verified` column exists but verification flow not implemented — see Section 15), login (password verification), JWT creation (sub=user_id, exp, iat, HS256), Google OAuth flow (Authlib, OpenID Connect, state token in session, auto-sets `email_verified=True`), `get_current_user` dependency (extract from Authorization Bearer header), cookie-based auth for page routes (access_token cookie set on OAuth callback, read in pages.py), `get_or_create_google_user` logic (find by google_id → find by email to link → create new), `terms_accepted_at` column exists but no acceptance flow or access gate — see Section 15. Reference: backend/api/auth.py, backend/services/auth_service.py, backend/api/pages.py, backend/schemas/auth.py
- [ ] T019 [US3] Create Mermaid `sequenceDiagram` for email registration and login per FR-005 — show Browser→FastAPI→auth_service→DB flow for both registration (check email, hash password, INSERT, create JWT) and login (SELECT, verify hash, create JWT). Use `rect rgb(...)` to group registration vs. login sub-flows. Add to Section 5 of specs/004-code-walkthrough-docs/walkthrough.md
- [ ] T020 [US3] Create Mermaid `sequenceDiagram` for Google OAuth per FR-005 — show Browser→FastAPI→Google→FastAPI→auth_service→DB flow: redirect to Google, consent, callback with code, exchange for token, get_or_create_google_user with `alt` block for new vs. existing user, set cookie, redirect to dashboard. Add to Section 5 of specs/004-code-walkthrough-docs/walkthrough.md

**Checkpoint**: US3 complete — reviewer can evaluate the full security implementation

---

## Phase 8: User Story 4 — Photo Upload Pipeline (Priority: P2)

**Goal**: Document the photo upload flow with a flowchart showing all validation gates and storage

**Independent Test**: Trace the flowchart against backend/api/projects.py upload endpoint and backend/services/upload_service.py

### Implementation

- [ ] T021 [US4] Write Section 6 narrative: describe multipart upload endpoint, per-file validation (MIME type ∈ {image/jpeg, image/png, image/webp}, size ≤ 10MB), filename parsing regex (`<person>_<seq>.<ext>`), get-or-create Person records, photo count enforcement (max 10 per person), disk storage pattern (`uploads/{user_id}/{project_id}/{filename}`), Photo DB record creation, and ownership verification via `get_user_project` dependency. Reference: backend/api/projects.py, backend/services/upload_service.py, backend/api/dependencies.py, backend/schemas/project.py
- [ ] T022 [US4] Create Mermaid `flowchart TD` for upload pipeline per FR-006 — show: Receive multipart POST → For each file: Validate MIME type (reject 400) → Validate size ≤10MB (reject 400) → Parse filename regex (reject 400 if invalid) → Get-or-create Person → Check photo count ≤10 (reject 400) → Save to disk → Create Photo record → Return PhotoUploadResponse. Show error paths branching to 400 responses. Add to Section 6 of specs/004-code-walkthrough-docs/walkthrough.md

**Checkpoint**: US4 complete — reviewer can verify file handling correctness

---

## Phase 9: User Story 5 — AI Moderation & Scenario Splitting (Priority: P2)

**Goal**: Document the Gemini-based moderation and splitting with a sequence diagram showing prompt construction and response parsing

**Independent Test**: Compare the sequence diagram against backend/services/moderation_service.py and backend/api/scenarios.py

### Implementation

- [ ] T023 [US5] Write Section 7 narrative: describe scenario submission endpoint (PUT), person name extraction from project, dual-section prompt structure (base MODERATION_SPLIT_PROMPT + conditional _CHARACTERS_SECTION), Gemini API call with `response_mime_type="application/json"`, response parsing (strip markdown fences, validate JSON), validation rules (max 15 segments, characters dict[str,str], per-segment persons list[str], name normalization to lowercase, unknown name filtering), content policy categories (violence, sexual content, hate speech, etc.), Scenario + Segment record creation, re-submission (delete old scenario first). Reference: backend/api/scenarios.py, backend/services/moderation_service.py, backend/schemas/scenario.py
- [ ] T024 [US5] Create Mermaid `sequenceDiagram` for moderation flow per FR-007 — show Browser→FastAPI(scenarios.py)→moderation_service→Gemini API flow: extract person names, build prompt (base + characters section), call Gemini, parse JSON response, validate structure, `alt` approved/rejected, create Scenario record, create Segment records (loop). Add to Section 7 of specs/004-code-walkthrough-docs/walkthrough.md

**Checkpoint**: US5 complete — reviewer understands AI integration and prompt engineering

---

## Phase 10: User Story 7 — API Route Map (Priority: P3)

**Goal**: Provide a complete API endpoint reference with methods, paths, auth requirements, and schema names

**Independent Test**: Compare every listed endpoint against actual route files in backend/api/

### Implementation

- [ ] T025 [P] [US7] Write Section 9 endpoint tables per FR-009 — create grouped tables for each router: Health (1 endpoint), Auth (5 endpoints), Projects (7 endpoints), Scenarios (2 endpoints), Generation (2 endpoints), Pages (7 endpoints). Each row: HTTP Method, Full Path, Auth Required (yes/no), Request Schema, Response Schema. Use exact paths from research.md Task 4 findings. Note that scenarios.py and generation.py share `/api/projects` prefix. Reference: backend/api/health.py, backend/api/auth.py, backend/api/projects.py, backend/api/scenarios.py, backend/api/generation.py, backend/api/pages.py, backend/api/dependencies.py
- [ ] T026 [US7] Create Mermaid `graph TD` route-to-service map — show 6 router boxes connecting to their service dependencies: auth.py→auth_service, projects.py→upload_service, scenarios.py→moderation_service, generation.py→pipeline_service, pages.py→(templates). Show shared `get_user_project` dependency used by projects, scenarios, and generation routers. Add to Section 9 of specs/004-code-walkthrough-docs/walkthrough.md

**Checkpoint**: US7 complete — reviewer can identify all API endpoints at a glance

---

## Phase 11: User Story 8 — Frontend & Template Architecture (Priority: P3)

**Goal**: Document template inheritance hierarchy and client-side JavaScript behaviors

**Independent Test**: Verify template descriptions against backend/templates/ and static/js/app.js

### Implementation

- [ ] T027 [P] [US8] Write Section 10 template narrative per FR-010 — describe base.html (responsive navbar, conditional auth links, flash messages, footer with `ad-zone--footer` placeholder div, CSS link), ad zone architecture (constitution mandates sidebar + banner + interstitial; only footer zone currently exists — cross-reference Section 15 implementation status), template inheritance (landing.html, dashboard.html, new_project.html, project_detail.html all extend base.html), key per-template features (landing: hero + how-it-works + auth forms; dashboard: project grid via JS fetch; new_project: form + dropzone + textarea; project_detail: upload + scenario + segments + generation + polling + video player). Reference: backend/templates/base.html, backend/templates/landing.html, backend/templates/dashboard.html, backend/templates/new_project.html, backend/templates/project_detail.html
- [ ] T028 [P] [US8] Write Section 10 JavaScript narrative — describe static/js/app.js behaviors: filename validation regex (`<person>_<number>.<ext>`), cookie-based token management, project form submission, drag-and-drop + file input upload with person grouping preview, scenario character count. Describe static/css/style.css: 522 lines, mobile-first responsive with CSS custom properties, key component styles. Reference: static/js/app.js, static/css/style.css

**Checkpoint**: US8 complete — reviewer understands full request lifecycle including frontend

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Complete remaining infrastructure sections, add file reference index, implementation status, and final validation

- [ ] T029 [P] Write Section 13: Test Infrastructure per FR-015 — describe conftest.py fixtures (setup_database autouse, override_get_db, client with AsyncClient/ASGI transport, test_user, auth_token/auth_headers, db_session), in-memory SQLite + StaticPool isolation, test directory structure (unit: test_upload_service, test_moderation_service, test_pipeline_service; integration: test_auth_api, test_project_api, test_scenario_api, test_generation_api; contract: empty placeholder). Mark contract tests as empty per FR-018. Reference: tests/conftest.py
- [ ] T030 [P] Write Section 14: Migrations per FR-016 — describe alembic.ini config (script_location=migrations, sqlite+aiosqlite default), migrations/env.py async runner (override sqlalchemy.url from settings, asyncio.run, offline+online modes, targets Base.metadata), and 3 existing migrations: create_users_table, add_project_person_photo_tables, add_scenario_segment_tables. Reference: alembic.ini, migrations/env.py
- [ ] T031 [P] Write Section 15: Implementation Status per FR-018 — create table of all placeholder/incomplete features from research.md Task 3 AND Task 7: launch_pipeline() is pass, no concatenation service, FinalVideoResponse stub, most ProjectStatus transitions unwired, contract tests empty, email verification column scaffolded but no send/verify flow, terms_accepted_at column scaffolded but no accept-terms endpoint or access gate, ad zones limited to single footer div (constitution requires sidebar + banner + interstitial). Add severity assessment and link to relevant sections
- [ ] T032 [P] Write Section 16: File Reference Index per FR-020 — create master table mapping all 27 backend Python files to their walkthrough sections, using the verified mapping from data-model.md. Verify 100% coverage per SC-002
- [ ] T033 Final validation pass: verify all 9 Mermaid diagrams render correctly by checking syntax against research.md patterns per FR-017, verify table of contents anchor links match actual section headings per FR-019, verify no secrets or API keys appear in document, verify all file references use correct paths
- [ ] T034 Run quickstart.md validation: confirm document matches quickstart.md section overview, verify reading instructions are accurate

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — create document scaffold first
- **Foundational (Phase 2)**: Depends on Phase 1 — writes infrastructure sections referenced by later phases
- **US1 Architecture (Phase 3)**: Depends on Phase 2 — references config, database, middleware, logging sections
- **US2 Data Model (Phase 4)**: Depends on Phase 1 — can start after scaffold exists
- **US6 Pipeline (Phase 5)**: Depends on Phase 1 — can start after scaffold exists
- **US9 State Machine (Phase 6)**: Depends on Phase 4 (US2) — adds to Section 4 after field/enum tables exist
- **US3 Auth (Phase 7)**: Depends on Phase 1 — can start after scaffold exists
- **US4 Upload (Phase 8)**: Depends on Phase 1 — can start after scaffold exists
- **US5 Moderation (Phase 9)**: Depends on Phase 1 — can start after scaffold exists
- **US7 API Reference (Phase 10)**: Depends on Phase 1 — can start after scaffold exists
- **US8 Frontend (Phase 11)**: Depends on Phase 1 — can start after scaffold exists
- **Polish (Phase 12)**: Depends on all user story phases — final validation needs all content in place

### User Story Dependencies

- **US1 (P1)**: Depends on Foundational (Phase 2) for infrastructure section context
- **US2 (P1)**: Independent — only needs document scaffold
- **US6 (P1)**: Independent — only needs document scaffold
- **US9 (P2)**: Depends on US2 — adds state diagram to Section 4 after field tables
- **US3 (P2)**: Independent — only needs document scaffold
- **US4 (P2)**: Independent — only needs document scaffold
- **US5 (P2)**: Independent — only needs document scaffold
- **US7 (P3)**: Independent — only needs document scaffold
- **US8 (P3)**: Independent — only needs document scaffold

### Within Each User Story

- Narrative content before Mermaid diagrams (narrative provides context for diagram)
- Single-section stories complete in 1–2 tasks
- Multi-diagram stories (US3 Auth) complete narrative → diagram 1 → diagram 2

### Parallel Opportunities

- **After Phase 2 completes**: US1 (T008-T009), US2 (T010-T013), US6 (T014-T015), US3 (T018-T020), US4 (T021-T022), US5 (T023-T024), US7 (T025-T026), US8 (T027-T028) can ALL start in parallel
- **Within US2**: T011 (field descriptions) and T012 (enum tables) are parallelizable
- **Within US7**: T025 (endpoint tables) can start in parallel with other stories
- **Within US8**: T027 (templates) and T028 (JavaScript) are parallelizable
- **Polish phase**: T029, T030, T031, T032 are all parallelizable

---

## Parallel Example: After Foundational Phase

```
# These can all run in parallel after Phase 2:
T008 [US1] Section 1: Architecture narrative
T010 [US2] Section 3: ER diagram
T014 [US6] Section 8: Pipeline narrative  
T018 [US3] Section 5: Auth narrative
T021 [US4] Section 6: Upload narrative
T023 [US5] Section 7: Moderation narrative
T025 [US7] Section 9: API endpoint tables
T027 [US8] Section 10: Template narrative
T028 [US8] Section 10: JavaScript narrative
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US6 Only)

1. Complete Phase 1: Setup (document scaffold)
2. Complete Phase 2: Foundational (infrastructure sections)
3. Complete Phase 3: US1 — Architecture Overview with diagram
4. Complete Phase 4: US2 — Data Model with ER diagram and enum tables
5. Complete Phase 5: US6 — Video Pipeline with flowchart
6. **STOP and VALIDATE**: Document covers the 3 most critical aspects — architecture, data, and core feature. Independently useful for review.

### Incremental Delivery

1. Setup + Foundational → Document scaffold with infrastructure sections
2. Add US1 → Architecture overview with diagram → Review-ready for system orientation
3. Add US2 → Data model with ER → Review-ready for data layer
4. Add US6 → Pipeline flowchart → Review-ready for core feature
5. Add US9 → State machine → Review-ready for lifecycle verification
6. Add US3 → Auth sequence diagrams → Review-ready for security review
7. Add US4 → Upload flowchart → Review-ready for file handling review
8. Add US5 → Moderation sequence → Review-ready for AI integration review
9. Add US7 → API reference tables → Review-ready for API surface review
10. Add US8 → Frontend docs → Complete walkthrough
11. Polish → File index, implementation status, validation → Final document

### Parallel Strategy

With multiple writers:
1. All complete Setup + Foundational together
2. Writer A: US1 (Architecture) + US6 (Pipeline)
3. Writer B: US2 (Data Model) + US9 (State Machine, after US2)
4. Writer C: US3 (Auth) + US4 (Upload) + US5 (Moderation)
5. Writer D: US7 (API Reference) + US8 (Frontend)
6. All collaborate on Polish phase

---

## Notes

- [P] tasks = different document sections, no content dependencies
- [Story] label maps task to specific user story for traceability
- Each user story produces 1–2 complete document sections
- All content targets a single file: specs/004-code-walkthrough-docs/walkthrough.md
- Verify Mermaid syntax renders in GitHub preview after each diagram task
- Reference source files listed in each task for accuracy verification
- Mark placeholder features explicitly per FR-018 findings in research.md
