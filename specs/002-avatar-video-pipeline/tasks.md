# Tasks: Avatar Video Generation Pipeline

**Input**: Design documents from `/specs/002-avatar-video-pipeline/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/api.yaml ✅, quickstart.md ✅

**Tests**: Included — Constitution Principle V (Test-First Development) is NON-NEGOTIABLE.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/` for Python source, `static/` for frontend assets, `tests/` for test suite
- Paths are relative to repository root (`avatarium/`)

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Create directory structure, initialize uv project, configure tooling

- [ ] T001 Create directory structure per plan.md: backend/{models,schemas,api,services,middleware,templates}/, static/{css,js,img}/, tests/{unit,integration,contract}/, migrations/versions/, uploads/, generated/
- [ ] T002 Initialize uv project with `uv init --name avatarium --python 3.12` and add all dependencies per research.md Decision 1 (fastapi, uvicorn[standard], jinja2, python-multipart, sqlalchemy[asyncio], aiosqlite, asyncpg, alembic, fal-client, google-generativeai, ffmpeg-python, authlib, python-jose[cryptography], passlib[bcrypt], httpx, python-dotenv, pydantic-settings, slowapi; dev: pytest, pytest-asyncio, pytest-cov, httpx, ruff, mypy)
- [ ] T003 [P] Create .env.example with all required variables per quickstart.md Section 3 (APP_SECRET_KEY, DATABASE_URL, FAL_KEY, GEMINI_API_KEY, JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRATION_MINUTES, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI)
- [ ] T004 [P] Configure ruff and mypy settings in pyproject.toml (target Python 3.12, line-length 100, src=["backend"], strict mypy)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Create backend/config.py using pydantic-settings BaseSettings to load all .env variables (APP_SECRET_KEY, DATABASE_URL, FAL_KEY, GEMINI_API_KEY, JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRATION_MINUTES, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, APP_ENV, APP_HOST, APP_PORT)
- [ ] T006 [P] Create backend/database.py with async SQLAlchemy engine (aiosqlite for dev), async sessionmaker, get_db dependency, and create_all helper
- [ ] T007 [P] Create backend/models/__init__.py with declarative Base using mapped_column, import registry for all model modules
- [ ] T008 Create backend/models/user.py with User entity per data-model.md (id UUID PK, email unique, display_name, hashed_password nullable, google_id nullable unique, email_verified default false, terms_accepted_at nullable, created_at, updated_at)
- [ ] T009 Setup Alembic migrations framework in migrations/ (alembic init, configure env.py for async SQLAlchemy, generate initial migration for User table)
- [ ] T010 [P] Create backend/schemas/auth.py with Pydantic v2 schemas per contracts/api.yaml: RegisterRequest, LoginRequest, AuthResponse, UserResponse
- [ ] T011 [P] Create backend/services/auth_service.py with password hashing (passlib bcrypt), JWT creation/verification (python-jose HS256), get_current_user dependency, register_user, authenticate_user functions
- [ ] T011a [P] Write integration tests for auth API in tests/integration/test_auth_api.py: test POST /api/auth/register (201/409/422), POST /api/auth/login (200/401), GET /api/auth/me (200/401), unauthenticated access (401), duplicate email registration (409). Tests MUST fail before T012 implementation.
- [ ] T012 Implement backend/api/auth.py with POST /api/auth/register (201/409/422), POST /api/auth/login (200/401), GET /api/auth/me (200/401) per contracts/api.yaml Auth section
- [ ] T013 [P] Create backend/middleware/__init__.py and backend/middleware/rate_limit.py using SlowAPI with configurable limits
- [ ] T014 [P] Create backend/api/health.py with GET /api/health returning {"status": "ok"} for deployment readiness checks
- [ ] T015 Create backend/main.py with FastAPI app factory, lifespan (DB init/shutdown), include routers (auth, health), mount static files, configure Jinja2 templates, attach rate-limit middleware, CORS
- [ ] T016 Create backend/templates/base.html with responsive HTML5 layout (viewport meta, mobile-first CSS link, nav bar, main content block, footer with ad zones, flash messages block)
- [ ] T017 [P] Create backend/templates/landing.html extending base.html with sign-in/register forms and hero section
- [ ] T018 [P] Create static/css/style.css with responsive base styles (mobile-first breakpoints at 768px/1024px, nav, form, button, flash-message, ad-zone, video-player component styles)
- [ ] T019 Create tests/conftest.py with pytest fixtures: async test client (httpx.AsyncClient), in-memory SQLite test database, test user factory, auth token helper, mock fal_client, mock google-generativeai
- [ ] T019a [P] Create backend/services/email_service.py with send_verification_email(user_id, email) stub (logs in dev, sends via SMTP/SES in prod), generate_verification_token(user_id) → signed URL token, verify_email_token(token) → user_id. Constitution: "Email verification is required for email/password registrations."
- [ ] T019b Add email verification endpoints to backend/api/auth.py: POST /api/auth/verify-email (accept token, set User.email_verified=True, 200/400/404), POST /api/auth/resend-verification (re-send email, 200/404). Registration (T012) must send verification email on success.
- [ ] T019c Create backend/middleware/terms_gate.py middleware/dependency that checks User.terms_accepted_at is non-null before allowing access to any protected endpoint (except GET /api/auth/me, POST /api/auth/terms). Returns 403 with {"detail": "Terms acceptance required"} if not accepted. Constitution: "Terms of Use must be presented and accepted before any platform features are accessible."
- [ ] T019d Add terms acceptance endpoint to backend/api/auth.py: POST /api/auth/terms (set User.terms_accepted_at=now(), 200/401). Integrate terms_gate dependency into all protected routers.
- [ ] T019e [P] Add structured security event logging to backend/services/auth_service.py and backend/middleware/rate_limit.py: log failed login attempts, registration failures, token decode failures, rate limit triggers. Use Python logging module with JSON-formatted security events. Constitution: "All security-relevant events are logged."

**Checkpoint**: Foundation ready — auth works with email verification and terms gate, app runs at http://localhost:8000, health endpoint responds, landing page renders. User story implementation can now begin.

---

## Phase 3: User Story 1 — Upload Named Images & Provide Scenario (Priority: P1) 🎯 MVP

**Goal**: Authenticated users create projects, upload named photos following `<personName>_<sequenceNumber>.<ext>` convention, write a scenario, and select a video style.

**Independent Test**: Upload photos with valid/invalid naming, verify person grouping, write scenario, select style, confirm project is saved in draft status.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T020 [P] [US1] Write unit tests for upload_service in tests/unit/test_upload_service.py: test filename parsing (person1_1.jpg → person="person1" seq=1), case-insensitive handling (PERSON1_1.JPG), rejection of invalid names (myphoto.jpg, no_number.jpg), file size validation (≤10MB), MIME type validation (jpeg/png/webp only), person grouping from multiple files, person-reference validation (FR-008: scenario mentioning "person3" when only person1/person2 uploaded → warning list)
- [ ] T021 [P] [US1] Write integration tests for project and photo API in tests/integration/test_project_api.py: test create project (201), list projects (200, user-scoped), get project detail (200/404), upload valid photos (201 with person grouping), upload invalid filename (400), upload oversized file (413), delete photo (204), delete project cascade (204)

### Implementation for User Story 1

- [ ] T022 [P] [US1] Create backend/models/project.py with Project (id, user_id FK, title, video_style enum, status enum with transitions, estimated_cost, actual_cost, timestamps), Person (id, project_id FK, name, unique on project_id+name), Photo (id, person_id FK, original_filename, sequence_number, file_path, file_size, mime_type, unique on person_id+sequence_number) per data-model.md
- [ ] T023 [P] [US1] Create backend/schemas/project.py with Pydantic v2 schemas per contracts/api.yaml: CreateProjectRequest, ProjectResponse, ProjectDetailResponse, ProjectListResponse, PersonResponse, PhotoResponse, PhotoGroupResponse, PhotoUploadResponse
- [ ] T024 [US1] Create backend/services/upload_service.py with parse_filename(name) → (person_name, sequence_number), validate_file(file) → check size ≤10MB and MIME type, group_files_by_person(files) → dict, save_photo(file, project_id) → Photo, ensuring user-scoped directory structure uploads/{user_id}/{project_id}/. Include MAX_PHOTOS_PER_PERSON=10 constant and validate_photo_count(existing_count, new_count) that raises ValueError if total would exceed 10. Constitution: "Maximum photos per person: 10 per project."
- [ ] T024a [US1] Add validate_person_references(scenario_text, person_names) → list[str] to backend/services/upload_service.py: check BOTH directions — (a) warn if uploaded person names are not mentioned in scenario text, (b) warn if scenario mentions names not present in uploads. FR-008 covers both directions.
- [ ] T025 [US1] Implement backend/api/projects.py with GET /api/projects (paginated, user-scoped), POST /api/projects (201), GET /api/projects/{id} (200/404), DELETE /api/projects/{id} (204/404), GET /api/projects/{id}/photos (grouped by person), POST /api/projects/{id}/photos (multipart upload, 201/400/413), DELETE /api/projects/{id}/photos/{photoId} (204/404) per contracts/api.yaml
- [ ] T026 [US1] Generate Alembic migration for Project, Person, and Photo tables
- [ ] T027 [US1] Create backend/templates/dashboard.html extending base.html with project list (title, style, status, date), "New Project" button, empty state message
- [ ] T028 [US1] Create backend/templates/new_project.html extending base.html with multi-file upload dropzone, filename validation feedback, person grouping preview, scenario textarea (max 10000 chars), style radio buttons (Animation/Movie-like), submit button
- [ ] T029 [US1] Create static/js/app.js with client-side filename validation (regex: /^[a-zA-Z0-9]+_\d+\.\w+$/), drag-and-drop upload handling, person grouping preview, file size check, form submission via fetch to POST /api/projects/{id}/photos

**Checkpoint**: User can register, log in, create a project, upload named photos, see person grouping, write a scenario, select a style. Project saved in "draft" status. All testable independently.

---

## Phase 4: User Story 2 — Scenario Moderation & Splitting (Priority: P1)

**Goal**: Submitted scenarios are moderated for content safety via Gemini 2.0 Flash, then split into ≤15 segments (~5 sec each) in a single API call. Users see the segment list before generation.

**Independent Test**: Submit clean and prohibited scenarios, verify moderation accept/reject, verify splitting produces coherent segments with correct count, verify segment list is displayed.

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T030 [P] [US2] Write unit tests for moderation_service in tests/unit/test_moderation_service.py: test clean scenario → approved + segments list, prohibited content → rejected with reason, scenario too long for 15 segments → rejected, combined moderation+splitting prompt format, Gemini response parsing (JSON extraction), error handling for Gemini API failures
- [ ] T031 [P] [US2] Write integration tests for scenario API in tests/integration/test_scenario_api.py: test PUT /api/projects/{id}/scenario (200 with segments), GET /api/projects/{id}/scenario (200 with moderation status + segments), rejected scenario (200 with rejection_reason), scenario without photos uploaded (400), unauthenticated access (401)

### Implementation for User Story 2

- [ ] T032 [P] [US2] Create backend/models/scenario.py with Scenario (id, project_id FK unique, text, moderation_status enum pending/approved/rejected, rejection_reason nullable, timestamps) and Segment (id, scenario_id FK, sequence_number 1-15, description, estimated_duration default 5.0, generation_status enum, unique on scenario_id+sequence_number) per data-model.md
- [ ] T033 [P] [US2] Create backend/schemas/scenario.py with Pydantic v2 schemas per contracts/api.yaml: SubmitScenarioRequest, ScenarioResponse, ScenarioDetailResponse, SegmentResponse
- [ ] T034 [US2] Create backend/services/moderation_service.py using google-generativeai SDK with Gemini 2.0 Flash: combined moderation+splitting prompt per research.md Decision 4, parse JSON response, create Scenario + Segment records, handle rejection with reason, enforce ≤15 segment limit
- [ ] T035 [US2] Implement backend/api/scenarios.py with PUT /api/projects/{id}/scenario (submit/re-submit, triggers moderation+splitting, 200/401/404/422) and GET /api/projects/{id}/scenario (200 with segments/401/404) per contracts/api.yaml
- [ ] T036 [US2] Generate Alembic migration for Scenario and Segment tables
- [ ] T037 [US2] Create backend/templates/project_detail.html extending base.html with project info header, scenario text display, moderation status badge (pending/approved/rejected with reason), numbered segment list with descriptions, "Start Generation" button (disabled until approved)

**Checkpoint**: User can submit a scenario, see moderation result, view segment breakdown. Prohibited content is blocked before any generation cost. All testable independently.

---

## Phase 5: User Story 3 — Iterative Video Generation Pipeline (Priority: P1)

**Goal**: After segment approval, the system generates images and video clips iteratively: first image → first video → extract last frame → next video → repeat. Users see real-time progress.

**Independent Test**: Submit a 2–3 segment project, verify image generation (Qwen), video generation (LTX Video), last-frame extraction (FFmpeg), sequential clip creation, progress tracking, retry on failure.

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T038 [P] [US3] Write unit tests for pipeline_service in tests/unit/test_pipeline_service.py: test pipeline orchestration sequence (image→video→frame→video→frame…), mock fal_client.subscribe calls, verify correct model IDs used (fal-ai/qwen-image, fal-ai/ltx-video-13b-distilled/image-to-video), test retry logic (1 automatic retry), test failure handling after retry exhausted, test status transitions (pending→generating→completed/failed), test last-frame extraction call
- [ ] T039 [P] [US3] Write integration tests for generation API in tests/integration/test_generation_api.py: test POST /api/projects/{id}/generate (202 accepted), test 400 when no approved scenario, test 409 when pipeline already running, test GET /api/projects/{id}/status (200 with per-segment progress), test unauthenticated access (401)

### Implementation for User Story 3

- [ ] T040 [P] [US3] Create backend/models/video.py with VideoClip (id, project_id FK, segment_id FK, sequence_number, input_image_path, video_file_path nullable, last_frame_path nullable, duration nullable, generation_cost nullable, status enum, retry_count default 0, error_message nullable, timestamps) and FinalVideo (id, project_id FK unique, file_path, total_duration, total_cost, file_size, created_at) per data-model.md
- [ ] T041 [P] [US3] Create backend/schemas/video.py with Pydantic v2 schemas per contracts/api.yaml: PipelineStatusResponse, ClipStatusResponse, FinalVideoResponse
- [ ] T042 [P] [US3] Create backend/services/image_gen_service.py using fal_client.subscribe("fal-ai/qwen-image", arguments={...}) to generate the initial image from person photos + first segment description + style directive, save to generated/{user_id}/{project_id}/images/
- [ ] T043 [P] [US3] Create backend/services/video_gen_service.py using fal_client.subscribe("fal-ai/ltx-video-13b-distilled/image-to-video", arguments={...}) to generate ~5-sec video clips from input image + segment description, audio disabled, save to generated/{user_id}/{project_id}/clips/. Include last-frame extraction via ffmpeg-python (`ffmpeg -sseof -0.1 -i clip.mp4 -vframes 1 last_frame.jpg`)
- [ ] T044 [US3] Create backend/services/pipeline_service.py orchestrating the full iterative pipeline: (1) generate initial image via image_gen_service, (2) for each segment: generate video via video_gen_service → extract last frame → store VideoClip record → update progress, (3) handle retry logic (retry_count ≤ 1), (4) update project status through transitions (generating → completed/failed), (5) store generated files in user-scoped directories
- [ ] T045 [US3] Implement backend/api/generation.py with POST /api/projects/{id}/generate (validate scenario approved + photos exist, launch pipeline as background task, return 202/400/401/404/409) and GET /api/projects/{id}/status (return current_segment, total_segments, per-clip status, 200/401/404) per contracts/api.yaml
- [ ] T046 [US3] Generate Alembic migration for VideoClip and FinalVideo tables
- [ ] T047 [US3] Add progress polling to backend/templates/project_detail.html (JavaScript setInterval polling GET /status every 5 seconds, update segment progress bars, show "Generating clip N of M" message, auto-refresh on completion) and extend static/js/app.js

**Checkpoint**: Full iterative pipeline works end-to-end: image gen → video gen → frame extraction → repeat. User sees per-segment progress. Failed clips retry once. All testable with mocked fal.ai responses.

---

## Phase 6: User Story 4 — Video Concatenation & Final Output (Priority: P2)

**Goal**: After all clips are generated, concatenate them into a single video via FFmpeg. The final video is previewable inline, downloadable, and stored in the user's dashboard.

**Independent Test**: Generate a multi-clip project, verify concatenation produces a single playable video, verify download works, verify inline player renders on desktop and mobile.

### Tests for User Story 4 ⚠️

- [ ] T048 [P] [US4] Write integration tests for video concat and download in tests/integration/test_generation_api.py: test concatenation triggers after all clips complete, test GET /api/projects/{id}/video (200 metadata/404), test GET /api/projects/{id}/video/download (200 binary stream/404), test GET /api/projects/{id}/clips/{clipId}/preview (200/404)

### Implementation for User Story 4

- [ ] T049 [US4] Create backend/services/video_concat_service.py using ffmpeg-python concat demuxer: accept list of clip file paths, concatenate in order, output to generated/{user_id}/{project_id}/final.mp4, create FinalVideo record with total_duration, total_cost (sum of clip costs), file_size
- [ ] T050 [US4] Add video endpoints to backend/api/generation.py: GET /api/projects/{id}/video (200 FinalVideoResponse/404), GET /api/projects/{id}/video/download (200 FileResponse streaming video/mp4), GET /api/projects/{id}/clips/{clipId}/preview (200 FileResponse) per contracts/api.yaml
- [ ] T051 [US4] Add video player and download section to backend/templates/project_detail.html: HTML5 `<video>` element with responsive sizing, download button, individual clip preview thumbnails, show only when project status is "completed"

**Checkpoint**: Complete user journey works: upload → moderate → generate → concatenate → watch → download. Video plays smoothly on desktop and mobile.

---

## Phase 7: User Story 5 — Cost-Optimized Processing (Priority: P2)

**Goal**: Display estimated cost before generation starts, track actual cost during pipeline execution, ensure lowest-cost models are used (LTX Video $0.04/clip, Qwen Image ~$0.02/image).

**Independent Test**: Create a project with N segments, verify estimated cost matches formula ($0.02 + N × $0.04), verify actual cost is tracked and displayed after generation.

### Tests for User Story 5 ⚠️

- [ ] T052 [P] [US5] Write unit tests for cost_service in tests/unit/test_cost_service.py: test estimate_cost(5 segments) = $0.22, estimate_cost(10) = $0.42, estimate_cost(15) = $0.62, test actual cost aggregation from VideoClip records, test cost includes image gen ($0.02) + video gen (N × $0.04) + LLM (~$0.001)

### Implementation for User Story 5

- [ ] T053 [US5] Create backend/services/cost_service.py with estimate_cost(segment_count) → Decimal using rates from research.md (image: $0.02, video: $0.04/clip, LLM: $0.001), calculate_actual_cost(project_id) → Decimal from VideoClip.generation_cost sum
- [ ] T054 [US5] Add cost estimate display to backend/templates/new_project.html (dynamic estimate based on segment count after splitting) and backend/templates/project_detail.html (estimated vs actual cost comparison after generation)
- [ ] T055 [US5] Integrate actual cost tracking into backend/services/pipeline_service.py: record generation_cost on each VideoClip ($0.04), record image gen cost ($0.02), update Project.actual_cost on pipeline completion

**Checkpoint**: Users see estimated cost before generating, actual cost after completion. Costs match expected rates from research.md.

---

## Phase 8: User Story 6 — Segment Review & Editing (Priority: P3)

**Goal**: Before generation, users can edit segment descriptions, remove segments, and reorder segments. Modified segment list is used for generation.

**Independent Test**: Split a scenario, edit one segment's text, remove another segment, verify renumbering, start generation and confirm modified segments are used.

### Tests for User Story 6 ⚠️

- [ ] T056 [P] [US6] Write integration tests for segment editing in tests/integration/test_scenario_api.py: test PATCH segment description, test DELETE segment (verify renumbering), test reorder segments, test generation uses edited segments, test edit after generation started (should be blocked)

### Implementation for User Story 6

- [ ] T057 [US6] Add segment edit/delete/reorder endpoints to backend/api/scenarios.py: PATCH /api/projects/{id}/scenario/segments/{segmentId} (update description), DELETE /api/projects/{id}/scenario/segments/{segmentId} (remove + renumber), PUT /api/projects/{id}/scenario/segments/reorder (accept ordered list of segment IDs)
- [ ] T058 [US6] Add inline segment editing UI to backend/templates/project_detail.html: editable text fields per segment, delete button with confirmation, drag-and-drop reorder, "Confirm Segments" button, disable editing once generation starts

**Checkpoint**: Users have full creative control over segments before generation. Editing is blocked during/after generation.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T059 [P] Create backend/templates/terms.html extending base.html with Terms of Use content and acceptance button (updates User.terms_accepted_at)
- [ ] T060 [P] Implement Google OAuth flow in backend/api/auth.py (GET /api/auth/google redirect, GET /api/auth/google/callback) and backend/services/auth_service.py (Authlib Google OAuth, account linking when google_id matches existing email) per contracts/api.yaml
- [ ] T061 [P] Create Dockerfile (multi-stage: uv install → slim runtime with FFmpeg) and docker-compose.yml (app + PostgreSQL for prod-like local env)
- [ ] T062 Write contract tests in tests/contract/test_api_contracts.py validating all API responses match Pydantic schemas from backend/schemas/
- [ ] T063 Security hardening across backend/: CORS configuration (allowed origins), HTTPS redirect middleware for production, security headers (X-Content-Type-Options, X-Frame-Options, CSP), input sanitization on scenario text, rate limit tuning
- [ ] T064 Run quickstart.md validation end-to-end: fresh clone → uv sync → .env setup → alembic upgrade → uvicorn → register → create project → upload → moderate → generate → download

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Foundational (Phase 2)
- **US2 (Phase 4)**: Depends on US1 (needs project with scenario)
- **US3 (Phase 5)**: Depends on US2 (needs approved segments)
- **US4 (Phase 6)**: Depends on US3 (needs generated clips)
- **US5 (Phase 7)**: T052–T054 depend on Foundational only (can start early); **T055 depends on T044 (pipeline_service.py from Phase 5)**
- **US6 (Phase 8)**: Depends on US2 — **can run in parallel with US3/US4/US5**
- **Polish (Phase 9)**: Depends on all desired user stories being complete

### User Story Dependencies

```
Phase 1 (Setup)
    │
Phase 2 (Foundational) ──── BLOCKS ALL ────┐
    │                                       │
Phase 3 (US1: Upload & Scenario)      Phase 7 (US5: Cost) ← can start early
    │                                       │
Phase 4 (US2: Moderation & Split)     Phase 8 (US6: Segment Edit) ← needs US2
    │
Phase 5 (US3: Video Generation)
    │
Phase 6 (US4: Concatenation)
    │
Phase 9 (Polish)
```

### Within Each User Story

1. Tests MUST be written and FAIL before implementation
2. Models before services
3. Services before API endpoints
4. Alembic migration after models
5. Templates/UI after API endpoints work
6. Story complete before moving to next priority

### Parallel Opportunities

**Phase 2** (after T005-T007 complete):
- T010, T011, T011a, T013, T014 can all run in parallel (different files, no deps)

**Phase 3** (US1 — all tests + models + schemas in parallel):
- T020, T021, T022, T023 can all run in parallel

**Phase 4** (US2 — all tests + models + schemas in parallel):
- T030, T031, T032, T033 can all run in parallel

**Phase 5** (US3 — six tasks in parallel):
- T038, T039, T040, T041, T042, T043 can all run in parallel

**Cross-story** (after Phase 2):
- US5 (cost) can start as soon as Foundational is complete
- US6 (segment edit) can start as soon as US2 is complete

---

## Parallel Example: User Story 3

```
# Launch all tests + models + schemas + independent services together:
T038: "Unit tests for pipeline_service in tests/unit/test_pipeline_service.py"
T039: "Integration tests for generation API in tests/integration/test_generation_api.py"
T040: "Create VideoClip/FinalVideo models in backend/models/video.py"
T041: "Create video schemas in backend/schemas/video.py"
T042: "Create image_gen_service in backend/services/image_gen_service.py"
T043: "Create video_gen_service in backend/services/video_gen_service.py"

# Then sequentially (depends on above):
T044: "Create pipeline_service orchestrator"
T045: "Implement generation API endpoints"
T046: "Generate Alembic migration"
T047: "Add progress polling UI"
```

---

## Implementation Strategy

### MVP First (User Stories 1–3 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: US1 — Upload & Scenario
4. **STOP and VALIDATE**: Test project creation + photo upload independently
5. Complete Phase 4: US2 — Moderation & Splitting
6. **STOP and VALIDATE**: Test scenario moderation independently
7. Complete Phase 5: US3 — Video Generation Pipeline
8. **STOP and VALIDATE**: Test iterative pipeline end-to-end (with mocked fal.ai)
9. **Deploy/demo MVP** — users can upload, moderate, generate clips

### Incremental Delivery

1. Setup + Foundational → Auth works, landing page renders
2. Add US1 → Project creation + photo uploads work → Demo
3. Add US2 → Scenario moderation + splitting work → Demo
4. Add US3 → Full pipeline generates clips → **MVP Demo!**
5. Add US4 → Concatenation + download work → **Feature-complete Demo**
6. Add US5 → Cost estimates shown → Business-ready
7. Add US6 → Segment editing → Creative control
8. Polish → Google OAuth, Docker, security hardening → **Production-ready**

### Parallel Team Strategy

With multiple developers after Foundational is complete:

- **Developer A**: US1 → US2 → US3 → US4 (main pipeline, sequential)
- **Developer B**: US5 (cost service, independent) then US6 (segment editing, after US2 done)
- **Developer C**: Polish tasks (T059–T064, independent)

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (Constitution Principle V: Test-First)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All file paths use user-scoped directories for privacy isolation (Constitution Principle I)
- fal.ai calls use `fal_client.subscribe()` pattern per research.md
- Gemini calls use combined moderation+splitting prompt per research.md Decision 4
