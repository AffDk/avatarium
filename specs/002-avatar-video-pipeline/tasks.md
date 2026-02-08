# Tasks: Avatar Video Generation Pipeline

**Input**: Design documents from `/specs/002-avatar-video-pipeline/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/api.yaml ✅, quickstart.md ✅

**Tests**: Included — Constitution Principle V mandates Test-First Development. Tests are written FIRST and must FAIL before implementation begins.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/` for server code, `static/` for assets, `tests/` for tests, `migrations/` for Alembic
- Structure follows plan.md project structure exactly

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependency installation, and basic scaffolding

- [ ] T001 Create project directory structure per plan.md (backend/, backend/models/, backend/schemas/, backend/api/, backend/services/, backend/middleware/, backend/templates/, static/css/, static/js/, static/img/, tests/unit/, tests/integration/, tests/contract/, migrations/)
- [ ] T002 Initialize Python 3.12 project with uv, add all production deps (fastapi, uvicorn[standard], jinja2, python-multipart, sqlalchemy[asyncio], aiosqlite, asyncpg, alembic, fal-client, google-generativeai, bcrypt, authlib, python-jose[cryptography], httpx, python-dotenv, pydantic, pydantic-settings, slowapi) and dev deps (pytest, pytest-asyncio, pytest-cov, httpx, ruff, mypy) per quickstart.md
- [ ] T003 [P] Create .env.example with all required environment variables per quickstart.md
- [ ] T004 [P] Create .gitignore (exclude .env, uploads/, generated/, __pycache__, *.pyc, .venv/, *.db, migrations/versions/*.pyc)
- [ ] T005 [P] Create README.md with project overview, setup instructions, and usage guide
- [ ] T006 [P] Create LICENSE (MIT)
- [ ] T007 [P] Configure pyproject.toml with pytest settings (asyncio_mode = "auto", testpaths = ["tests"]) and ruff config

**Checkpoint**: Project scaffold exists, all dependencies installed, ready to write code

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T008 [P] Create test fixtures (async test client, in-memory SQLite with StaticPool, auth token helper, test user factory) in tests/conftest.py
- [ ] T009 [P] Write integration tests for auth API (register 201, login 200, duplicate email 409, invalid credentials 401, get current user 200/401, terms acceptance) in tests/integration/test_auth_api.py

### Implementation for Foundational

- [ ] T010 Implement configuration via pydantic-settings BaseSettings (app, database, fal_key, fal_video_model, gemini_api_key, gemini_model, google_oauth, jwt, rate_limit_default) in backend/config.py
- [ ] T011 [P] Setup async database engine and session factory (create_async_engine, async_sessionmaker, get_db dependency) in backend/database.py
- [ ] T012 [P] Create User model with all fields per data-model.md (id UUID PK, email unique, display_name, hashed_password nullable, google_id nullable unique, email_verified, terms_accepted_at, created_at, updated_at) in backend/models/user.py
- [ ] T013 [P] Create auth Pydantic schemas (RegisterRequest, LoginRequest, AuthResponse, UserResponse) matching api.yaml in backend/schemas/auth.py
- [ ] T014 Implement auth service (bcrypt.hashpw/checkpw for password hashing per research.md Decision 10, python-jose JWT create/verify, Google OAuth via Authlib) in backend/services/auth_service.py
- [ ] T015 Implement auth API routes (POST register 201, POST login 200, GET google redirect, GET google/callback, GET me 200) matching api.yaml in backend/api/auth.py
- [ ] T016 [P] Setup rate limiting middleware using SlowAPI with configurable default from settings.rate_limit_default in backend/middleware/rate_limit.py
- [ ] T017 [P] Create health check endpoint (GET /api/health → 200) in backend/api/health.py
- [ ] T018 Create FastAPI app factory with lifespan (DB table creation), CORS, rate limiter, Jinja2 templates, static files, route registration in backend/main.py
- [ ] T019 [P] Create base.html with responsive meta viewport, nav bar, ad zones, CSS/JS includes in backend/templates/base.html
- [ ] T020 [P] Create landing.html with sign-in/register form extending base.html in backend/templates/landing.html
- [ ] T021 [P] Create static/css/style.css with responsive styles (mobile-first, 320px+ breakpoints, ad zone styling)
- [ ] T022 Setup Alembic migrations framework (alembic init, configure env.py for async SQLAlchemy, create initial migration for users table) in migrations/

**Checkpoint**: Auth working, test client ready, foundation complete — user story implementation can now begin

---

## Phase 3: User Story 1 — Upload Named Images & Provide Scenario (Priority: P1) 🎯 MVP

**Goal**: Authenticated users create projects, upload photos with `<personName>_<seq>.<ext>` naming convention, write a scenario, select "Animation" or "Movie-like" style

**Independent Test**: Upload images with correct/incorrect naming, verify person grouping, write scenario referencing persons, select style, verify validation feedback at each step

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T023 [P] [US1] Write unit tests for upload service (parse valid names, reject invalid names, case-insensitive grouping per FR-003, file size/type validation per FR-005, person reference mismatch warnings per FR-008) in tests/unit/test_upload_service.py
- [ ] T024 [P] [US1] Write integration tests for project API (create project 201, list projects 200, get project 200, delete project 204, upload photos 201, upload invalid naming 400, upload oversized file 413, delete photo 204, unauthorized 401) in tests/integration/test_project_api.py

### Implementation for User Story 1

- [ ] T025 [P] [US1] Create Project model (id UUID, user_id FK, title, video_style enum animation/movie_like, status enum with transitions per data-model.md, estimated_cost, actual_cost, timestamps) in backend/models/project.py
- [ ] T026 [P] [US1] Create Person model (id UUID, project_id FK, name, unique constraint on project_id+name) and Photo model (id UUID, person_id FK, original_filename, sequence_number, file_path, file_size, mime_type, unique constraint on person_id+sequence_number) in backend/models/project.py
- [ ] T027 [P] [US1] Create project Pydantic schemas (CreateProjectRequest, ProjectResponse, ProjectDetailResponse, ProjectListResponse, PersonResponse, PhotoResponse, PhotoGroupResponse, PhotoUploadResponse) matching api.yaml in backend/schemas/project.py
- [ ] T028 [US1] Implement upload service (validate file size ≤10MB per FR-005, validate mime type jpeg/png/webp, parse `<personName>_<seq>.<ext>` case-insensitively per FR-003, group by person per FR-002, detect person-scenario mismatches per FR-008) in backend/services/upload_service.py
- [ ] T029 [US1] Implement projects API routes (GET /api/projects paginated, POST /api/projects 201, GET /api/projects/{id} 200, DELETE /api/projects/{id} 204, GET /api/projects/{id}/photos grouped, POST /api/projects/{id}/photos multipart 201, DELETE /api/projects/{id}/photos/{photoId} 204) matching api.yaml in backend/api/projects.py
- [ ] T030 [US1] Register project routes in backend/main.py and export models in backend/models/__init__.py
- [ ] T031 [P] [US1] Create dashboard.html (user's project list with status badges, create new project link) in backend/templates/dashboard.html
- [ ] T032 [P] [US1] Create new_project.html (multi-file upload with drag-drop, scenario textarea max 10000 chars per FR-007, style radio buttons Animation/Movie-like per FR-009, submit button) in backend/templates/new_project.html
- [ ] T033 [US1] Create Alembic migration for projects, persons, photos tables
- [ ] T034 [P] [US1] Add upload handling and form validation JS in static/js/app.js

**Checkpoint**: Users can register, log in, create projects, upload photos with naming validation, write scenarios, select styles. US1 is fully functional and testable independently.

---

## Phase 4: User Story 2 — Scenario Moderation & Splitting (Priority: P1)

**Goal**: System screens scenario via Gemini LLM for prohibited content, then splits approved scenarios into ≤15 segments (~5 sec each) in a single API call per FR-013

**Independent Test**: Submit clean scenario → approved + split into segments. Submit violent/sexual content → rejected with explanation before any cost. Submit overly long scenario → rejected for >15 segments.

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T035 [P] [US2] Write unit tests for moderation service (approved scenario → segments, rejected scenario → reason, combined prompt per FR-013, >15 segments rejection per FR-016, Gemini response parsing, malformed response handling) in tests/unit/test_moderation_service.py
- [ ] T036 [P] [US2] Write integration tests for scenario API (submit scenario 200, get scenario with segments 200, resubmit scenario, unauthorized 401, project not found 404) in tests/integration/test_scenario_api.py

### Implementation for User Story 2

- [ ] T037 [P] [US2] Create Scenario model (id UUID, project_id FK unique, text, moderation_status enum pending/approved/rejected, rejection_reason, timestamps) and Segment model (id UUID, scenario_id FK, sequence_number 1-15, description, estimated_duration 5.0, generation_status enum, unique constraint on scenario_id+sequence_number) per data-model.md in backend/models/scenario.py
- [ ] T038 [P] [US2] Create scenario Pydantic schemas (SubmitScenarioRequest, ScenarioResponse, ScenarioDetailResponse, SegmentResponse) matching api.yaml in backend/schemas/scenario.py
- [ ] T039 [US2] Implement moderation service (configure google-generativeai with settings.gemini_model, combined moderation+splitting prompt per research.md Decision 4, parse JSON response, create segments, enforce ≤15 segment limit per FR-015) in backend/services/moderation_service.py
- [ ] T040 [US2] Implement scenario API routes (PUT /api/projects/{id}/scenario 200 triggers moderation+split, GET /api/projects/{id}/scenario includes segments) matching api.yaml in backend/api/scenarios.py
- [ ] T041 [US2] Register scenario routes in backend/main.py and export Scenario/Segment models in backend/models/__init__.py
- [ ] T042 [US2] Create Alembic migration for scenarios, segments tables
- [ ] T043 [US2] Update project_detail.html to show moderation status, rejection reason, and segment list with sequence numbers and descriptions per FR-017

**Checkpoint**: Scenarios are screened for prohibited content and split into segments. Users see segment list before generation. US2 is fully functional and testable independently.

---

## Phase 5: User Story 3 — Iterative Video Generation Pipeline (Priority: P1)

**Goal**: System generates initial image via fal.ai Qwen Image, then iteratively generates ~5-sec video clips via fal.ai LTX Video, extracting last frames for visual continuity per FR-018–FR-024

**Independent Test**: Submit 2-3 segment project, verify sequential clip generation, confirm last-frame extraction works, check style reflected, verify retry on failure, verify progress polling

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T044 [P] [US3] Write unit tests for image gen service (fal.ai Qwen Image call with style directive, download file, error handling) in tests/unit/test_pipeline_service.py
- [ ] T045 [P] [US3] Write unit tests for video gen service (fal.ai LTX Video call via settings.fal_video_model, ffmpeg last-frame extraction via subprocess, download file) in tests/unit/test_pipeline_service.py
- [ ] T046 [P] [US3] Write unit tests for pipeline orchestration (correct sequence: image→video→lastframe→repeat, retry once on failure per FR-024, all segments processed, progress tracking) in tests/unit/test_pipeline_service.py
- [ ] T047 [P] [US3] Write integration tests for generation API (POST generate 202, POST generate missing scenario 400, POST generate already running 409, GET status 200, unauthorized 401) in tests/integration/test_generation_api.py

### Implementation for User Story 3

- [ ] T048 [P] [US3] Create VideoClip model (id UUID, project_id FK, segment_id FK, sequence_number, input_image_path, video_file_path, last_frame_path, duration, generation_cost, status enum, retry_count default 0, error_message, timestamps) per data-model.md in backend/models/video.py
- [ ] T049 [P] [US3] Create video Pydantic schemas (GenerationAcceptedResponse, PipelineStatusResponse, ClipStatusResponse) matching api.yaml in backend/schemas/video.py
- [ ] T050 [P] [US3] Implement image gen service (fal_client.subscribe "fal-ai/qwen-image" with style directive, text prompt incorporating person names + segment description per FR-018, download generated image) in backend/services/image_gen_service.py
- [ ] T051 [P] [US3] Implement video gen service (fal_client.subscribe using settings.fal_video_model, 480p resolution 854×480 per FR-029, 121 frames ~5sec at 24fps, audio disabled per FR-022, last-frame extraction via subprocess ffmpeg per FR-020) in backend/services/video_gen_service.py
- [ ] T052 [US3] Implement pipeline orchestration service (pure orchestration — no DB dependency, iterate segments: generate_initial_image→generate_video_clip→extract_last_frame→repeat, MAX_RETRIES=1 per FR-024, return list of result dicts) in backend/services/pipeline_service.py
- [ ] T053 [US3] Implement generation API routes (POST /api/projects/{id}/generate 202 with async background task, GET /api/projects/{id}/status 200 with per-segment progress per FR-023, guard missing scenario/photos 400, guard already running 409) matching api.yaml in backend/api/generation.py
- [ ] T054 [US3] Register generation routes in backend/main.py and export VideoClip model in backend/models/__init__.py
- [ ] T055 [US3] Create Alembic migration for video_clips table
- [ ] T056 [US3] Add progress polling UI (segment progress bar "Generating clip 3 of 10" per FR-023, per-clip status indicators, error display) to backend/templates/project_detail.html
- [ ] T057 [P] [US3] Add progress polling JS (poll GET /status on interval, update progress bar, handle completion/failure) to static/js/app.js

**Checkpoint**: Full iterative pipeline generates clips with visual continuity. Users see progress per segment. US3 is fully functional and testable independently.

---

## Phase 6: User Story 4 — Video Concatenation & Final Output (Priority: P2)

**Goal**: Concatenate all clips into one continuous video via FFmpeg; provide inline preview, download, and dashboard display per FR-025–FR-026

**Independent Test**: Generate multi-segment project, verify concatenated video plays smoothly, verify download works, verify responsive video player on mobile viewports

### Tests for User Story 4 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T058 [P] [US4] Write unit tests for video concat service (ffmpeg concat demuxer call, output file creation, total duration calculation, error handling) in tests/unit/test_concat_service.py
- [ ] T059 [P] [US4] Write integration tests for video endpoints (GET video metadata 200, GET download stream 200, GET clip preview 200, not found 404, unauthorized 401) in tests/integration/test_video_api.py

### Implementation for User Story 4

- [ ] T060 [P] [US4] Add FinalVideo model (id UUID, project_id FK unique, file_path, total_duration, total_cost, file_size, created_at) per data-model.md to backend/models/video.py
- [ ] T061 [US4] Implement video concat service (create ffmpeg concat demuxer file list, subprocess.run ffmpeg -f concat per research.md Decision 5, calculate total duration, return output path) in backend/services/video_concat_service.py
- [ ] T062 [US4] Wire concatenation into pipeline as final step — after all clips complete, call concat service, create FinalVideo record, update project status to "completed" in backend/services/pipeline_service.py
- [ ] T063 [US4] Add video endpoints (GET /api/projects/{id}/video metadata, GET /api/projects/{id}/video/download file stream, GET /api/projects/{id}/clips/{clipId}/preview stream) matching api.yaml in backend/api/generation.py
- [ ] T064 [US4] Create Alembic migration for final_videos table and export FinalVideo in backend/models/__init__.py
- [ ] T065 [US4] Add responsive video player (HTML5 video element, responsive 320px+ per FR-026, download button, per-clip preview thumbnails) to backend/templates/project_detail.html
- [ ] T066 [US4] Update dashboard.html to show project completion status and "Watch Video" link for completed projects

**Checkpoint**: Complete end-to-end flow: upload → moderate → generate → concatenate → play/download. US4 is fully functional and testable independently.

---

## Phase 7: User Story 5 — Cost-Optimized Processing (Priority: P2)

**Goal**: Display estimated cost before generation; track actual cost per clip; enforce lowest-cost model selection per FR-027–FR-029

**Independent Test**: Create project with N segments, verify estimate shown before generation, verify actual cost stays within estimate, verify 480p default

### Tests for User Story 5 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T067 [P] [US5] Write unit tests for cost service (estimate for 5/10/15 segments matching spec cost table, per-clip cost tracking, total cost aggregation) in tests/unit/test_cost_service.py

### Implementation for User Story 5

- [ ] T068 [P] [US5] Implement cost estimation service (image gen ~$0.02, video gen ~$0.04/clip, LLM ~$0.001, total estimate by segment count) per spec cost table in backend/services/cost_service.py
- [ ] T069 [US5] Wire cost estimate into generation flow — calculate estimated_cost when scenario is split, store on Project.estimated_cost, return in status API in backend/api/generation.py
- [ ] T070 [US5] Track actual cost per clip — update VideoClip.generation_cost after each fal.ai call in backend/services/pipeline_service.py
- [ ] T071 [US5] Add cost estimate display to project_detail.html (show "Estimated cost: $X.XX" before "Generate" button per FR-028)
- [ ] T072 [US5] Calculate and store FinalVideo.total_cost as sum of all VideoClip.generation_cost after concatenation

**Checkpoint**: Users see cost estimates before generation. Actual costs tracked and stored. US5 is fully functional and testable independently.

---

## Phase 8: User Story 6 — Segment Review & Editing (Priority: P3)

**Goal**: Users can edit segment descriptions, remove segments, and reorder segments before generation per FR-030–FR-031

**Independent Test**: Split scenario, edit segment text, remove a segment, reorder segments, verify generation uses modified list, verify 409 if editing during generation

### Tests for User Story 6 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T073 [P] [US6] Write integration tests for segment editing (PATCH segment 200, DELETE segment 200 with renumbering, PUT reorder 200, edit during generation 409, segment not found 404, unauthorized 401) in tests/integration/test_segment_api.py

### Implementation for User Story 6

- [ ] T074 [P] [US6] Create segment editing Pydantic schemas (UpdateSegmentRequest, ReorderSegmentsRequest) matching api.yaml in backend/schemas/scenario.py
- [ ] T075 [US6] Implement segment edit endpoint (PATCH /api/projects/{id}/scenario/segments/{segmentId} 200, validate description 1-5000 chars) in backend/api/scenarios.py
- [ ] T076 [US6] Implement segment delete endpoint (DELETE segment 200, renumber remaining segments, return updated ScenarioDetailResponse) in backend/api/scenarios.py
- [ ] T077 [US6] Implement segment reorder endpoint (PUT /api/projects/{id}/scenario/segments/reorder 200, validate all segment IDs provided, update sequence_numbers) in backend/api/scenarios.py
- [ ] T078 [US6] Add 409 conflict guard — reject segment edits if project status is "generating", "concatenating", or "completed" in all segment endpoints
- [ ] T079 [US6] Add segment editor UI (inline text editing, drag-to-reorder, delete button with confirmation, "Confirm & Generate" button) to backend/templates/project_detail.html

**Checkpoint**: Users have full creative control over segments before committing to generation. US6 is fully functional and testable independently.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Deployment, documentation, and improvements that affect multiple user stories

- [ ] T080 [P] Create Dockerfile for production deployment (Python 3.12 slim, apt install ffmpeg, uv sync, uvicorn entrypoint) in Dockerfile
- [ ] T081 [P] Create docker-compose.yml for local development (app + PostgreSQL services) in docker-compose.yml
- [ ] T082 [P] Create terms.html template for Terms of Use page (required before platform access per data-model.md User.terms_accepted_at) in backend/templates/terms.html
- [ ] T083 [P] Implement video deletion endpoint (DELETE /api/projects/{id}/video 204, cascade-delete clips; project deletion cascade-deletes all videos) per FR-026a in backend/api/generation.py
- [ ] T084 Code cleanup and refactoring across all modules (remove dead code, consistent error handling, docstrings)
- [ ] T085 Security hardening (enforce HTTPS in production, add security headers, validate all user inputs, review file upload paths for traversal)
- [ ] T086 [P] Performance test — verify 10-segment pipeline completes within 20 minutes per SC-001 and within $1.00 budget per SC-004
- [ ] T087 Run quickstart.md validation (fresh clone, uv sync, configure .env, alembic upgrade, run server, run tests, verify all steps work)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — **BLOCKS all user stories**
- **User Story 1 (Phase 3)**: Depends on Phase 2 — No dependencies on other stories
- **User Story 2 (Phase 4)**: Depends on Phase 2 — Uses Project model from US1 but can implement own fixtures
- **User Story 3 (Phase 5)**: Depends on Phase 2 — Uses Segment model from US2 for context but pipeline service is pure orchestration
- **User Story 4 (Phase 6)**: Depends on US3 (needs clips to concatenate)
- **User Story 5 (Phase 7)**: Depends on US3 (cost tracking wired into pipeline)
- **User Story 6 (Phase 8)**: Depends on US2 (modifies segments created by splitting)
- **Polish (Phase 9)**: Depends on all desired user stories being complete

### User Story Independence

| Story | Can Start After | Integrates With | Independently Testable? |
|-------|----------------|-----------------|------------------------|
| US1 (Upload) | Phase 2 | None | ✅ Yes |
| US2 (Moderation) | Phase 2 | US1 (Project) | ✅ Yes (own fixtures) |
| US3 (Pipeline) | Phase 2 | US2 (Segments) | ✅ Yes (mocked inputs) |
| US4 (Concat) | US3 | US3 (Clips) | ✅ Yes (mock clips) |
| US5 (Cost) | US3 | US3 (Pipeline) | ✅ Yes (unit testable) |
| US6 (Editing) | US2 | US2 (Segments) | ✅ Yes (own fixtures) |

### Within Each User Story

1. Tests FIRST — write tests, ensure they **FAIL** before implementation
2. Models before services
3. Services before endpoints
4. Core implementation before UI
5. Alembic migration after models are stable
6. Story checkpoint: verify independently

### Parallel Opportunities

- All Setup tasks T003–T007 marked [P] can run in parallel
- Foundational implementation: T011/T012/T013/T016/T017/T019/T020/T021 all [P]
- Within each user story: all tasks marked [P] can run in parallel
- US1 and US2 can proceed in parallel after Phase 2 (different models, different services, different endpoints)
- US4 and US5 can proceed in parallel after US3 (US4=concat, US5=cost — different services)

---

## Parallel Example: User Story 1

```bash
# Launch all tests for US1 together (both [P]):
Task T023: "Unit tests for upload service in tests/unit/test_upload_service.py"
Task T024: "Integration tests for project API in tests/integration/test_project_api.py"

# Launch all models + schemas for US1 together (all [P]):
Task T025: "Create Project model in backend/models/project.py"
Task T026: "Create Person and Photo models in backend/models/project.py"
Task T027: "Create project Pydantic schemas in backend/schemas/project.py"

# Then sequential: service → API → registration → migration
Task T028 → T029 → T030 → T033

# UI tasks are parallel with each other (all [P]):
Task T031: "dashboard.html"
Task T032: "new_project.html"
Task T034: "app.js upload handling"
```

## Parallel Example: User Story 3

```bash
# Launch all tests together (all [P]):
Task T044, T045, T046, T047

# Launch all independent models + schemas + services (all [P]):
Task T048: "VideoClip model"
Task T049: "Video Pydantic schemas"
Task T050: "Image gen service"
Task T051: "Video gen service"

# Then sequential: orchestration → API → registration → migration → UI
Task T052 → T053 → T054 → T055 → T056

# JS is parallel with UI:
Task T057: "Progress polling JS"
```

---

## Implementation Strategy

### MVP First (User Stories 1–3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (**CRITICAL** — blocks all stories)
3. Complete Phase 3: User Story 1 (Upload) → **Test independently**
4. Complete Phase 4: User Story 2 (Moderation) → **Test independently**
5. Complete Phase 5: User Story 3 (Pipeline) → **Test independently**
6. **STOP and VALIDATE**: Full pipeline working end-to-end (upload → moderate → generate clips)
7. Deploy/demo if ready — this is the core MVP

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (Upload) → Test → First increment (users can create projects)
3. Add US2 (Moderation) → Test → Second increment (scenarios screened + split)
4. Add US3 (Pipeline) → Test → **MVP!** (clips generated with progress)
5. Add US4 (Concat) → Test → Full video delivery
6. Add US5 (Cost) → Test → Cost transparency
7. Add US6 (Editing) → Test → Creative control
8. Polish → Production ready

### Parallel Team Strategy

With multiple developers after Phase 2:

- **Developer A**: US1 (Upload) → US4 (Concat)
- **Developer B**: US2 (Moderation) → US6 (Editing)
- **Developer C**: US3 (Pipeline) → US5 (Cost)

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks within the same phase
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Constitution V: Write tests FIRST, verify they FAIL, then implement
- bcrypt used directly (not passlib) per research.md Decision 10
- FFmpeg via subprocess.run (not ffmpeg-python) per research.md Decision 5
- Gemini model configurable via settings.gemini_model (default: gemini-2.5-flash)
- fal.ai video model configurable via settings.fal_video_model (default: fal-ai/ltx-video-13b-distilled/image-to-video)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
