# Implementation Plan: Avatar Video Generation Pipeline

**Branch**: `002-avatar-video-pipeline` | **Date**: 2026-02-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-avatar-video-pipeline/spec.md`

## Summary

Build a web application where users upload named photos of people, write a video scenario, and select a visual style (Animation or Movie-like). The system moderates the scenario via Google Gemini, splits it into ≤15 segments (~5 sec each), iteratively generates images and video clips via fal.ai, and concatenates all clips into a single final video. The entire stack uses Python (FastAPI backend, Jinja2 templates frontend), managed with `uv` for virtual environments and package installation, optimized for absolute minimum generation cost (~$0.04/clip via LTX Video 13B Distilled).

## Technical Context

**Language/Version**: Python 3.12+
**Package Manager**: uv (for virtual environment creation and package management)
**Primary Dependencies**: FastAPI, Uvicorn, Jinja2, python-multipart, google-generativeai, fal-client, ffmpeg-python, python-jose[cryptography], passlib[bcrypt], python-dotenv, SQLAlchemy, aiosqlite, asyncpg, httpx, Authlib, SlowAPI, pydantic-settings
**Storage**: SQLite (dev) / PostgreSQL (prod) via SQLAlchemy async; file storage on local disk (dev) / cloud object storage (prod)
**Testing**: pytest, pytest-asyncio, pytest-cov, httpx (for async test client)
**Target Platform**: Linux server (deployment), Windows/macOS (development)
**Project Type**: Web application (backend API + server-rendered frontend)
**Performance Goals**: Handle 50 concurrent users; API responses <500ms for non-generation endpoints; generation pipeline progress updates via polling or SSE
**Constraints**: Generation cost <$1.00 per 10-segment project; max 15 segments; max 10 MB per photo; HTTPS enforced in production
**Scale/Scope**: MVP targeting ~100 users; 5 main pages (landing, dashboard, new project, project detail, terms); 31 functional requirements

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Constitution Principle | Status | Notes |
|---|---|---|---|
| I | Privacy-First Architecture | ✅ PASS | All project data (photos, videos, scenarios) scoped to authenticated user. SQLAlchemy models enforce user_id FK on every query. File storage uses user-scoped directories. |
| II | Content Safety | ✅ PASS | Gemini moderation runs before any generation begins. Rejected scenarios incur zero generation cost. |
| III | Security by Default | ✅ PASS | API keys stored in env vars / `.env` (gitignored). HTTPS enforced in prod. Rate limiting via SlowAPI. Security events logged. |
| IV | Responsive & Accessible Design | ✅ PASS | Jinja2 templates use responsive CSS. Ad placement zones in layout. Mobile-first design. |
| V | Test-First Development | ✅ PASS | pytest with async support. Tests for moderation, file validation, naming convention, access control, pipeline steps. |
| VI | Deployment Readiness | ✅ PASS | Dockerized deployment. `uv` for reproducible environments. Health-check endpoint. Env-separated config. |
| VII | Professional Standards | ✅ PASS | Clean project structure, meaningful commits, documented API, README with setup instructions. |

**Gate result: ALL PASS** — proceed to Phase 0.

### Post-Design Re-evaluation (after Phase 1)

| # | Principle | Status | Design Artifact |
|---|-----------|--------|-----------------|
| I | Privacy-First | ✅ PASS | `data-model.md`: User.id FK on Project; all queries scoped. API contract enforces bearer auth on every endpoint. |
| II | Content Safety | ✅ PASS | `api.yaml`: PUT `/scenario` triggers moderation before splitting. Pipeline endpoint returns 400 if scenario not approved. |
| III | Security by Default | ✅ PASS | `api.yaml`: `bearerAuth` security scheme on all protected endpoints. `.env.example` lists secrets without values. |
| IV | Responsive Design | ✅ PASS | `quickstart.md`: Jinja2 templates with responsive CSS confirmed in project structure. |
| V | Test-First | ✅ PASS | `plan.md` structure: unit, integration, contract test directories pre-planned. `quickstart.md` includes test commands. |
| VI | Deployment Ready | ✅ PASS | `quickstart.md`: Full uv-based setup, Alembic migrations, Dockerfile in project structure. |
| VII | Professional Standards | ✅ PASS | `README.md` and `LICENSE` created. OpenAPI contract in `contracts/api.yaml`. |

**Post-design gate: ALL PASS** — proceed to Phase 2 (task breakdown via `/speckit.tasks`).

## Project Structure

### Documentation (this feature)

```text
specs/002-avatar-video-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API contracts)
│   └── api.yaml         # OpenAPI 3.0 specification
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
avatarium/
├── .env.example             # Template for environment variables (committed)
├── .gitignore               # Excludes .env, uploads, generated, __pycache__, etc.
├── pyproject.toml           # Project metadata, dependencies, scripts (uv-managed)
├── uv.lock                  # Lockfile for reproducible installs
├── README.md                # Project overview, setup, and usage instructions
├── LICENSE                  # MIT License
├── Dockerfile               # Production container image
├── docker-compose.yml       # Local development with all services
│
├── backend/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory, lifespan, middleware
│   ├── config.py            # Settings from environment variables (pydantic-settings)
│   ├── database.py          # SQLAlchemy async engine, session factory
│   │
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── user.py          # User, terms acceptance
│   │   ├── project.py       # Project, Person, Photo
│   │   ├── scenario.py      # Scenario, Segment
│   │   └── video.py         # VideoClip, FinalVideo
│   │
│   ├── schemas/             # Pydantic request/response schemas
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── project.py
│   │   ├── scenario.py
│   │   └── video.py
│   │
│   ├── api/                 # FastAPI route handlers
│   │   ├── __init__.py
│   │   ├── auth.py          # Login, register, Google OAuth, terms
│   │   ├── projects.py      # CRUD for projects, photo upload
│   │   ├── scenarios.py     # Submit, moderate, split
│   │   ├── generation.py    # Start pipeline, check progress
│   │   └── health.py        # Health-check endpoint
│   │
│   ├── services/            # Business logic (testable, framework-agnostic)
│   │   ├── __init__.py
│   │   ├── auth_service.py       # Password hashing, JWT, OAuth
│   │   ├── upload_service.py     # File validation, naming convention parser
│   │   ├── moderation_service.py # Gemini content moderation + splitting
│   │   ├── image_gen_service.py  # fal.ai image generation
│   │   ├── video_gen_service.py  # fal.ai video generation
│   │   ├── pipeline_service.py   # Orchestrates the iterative pipeline
│   │   ├── video_concat_service.py # FFmpeg concatenation
│   │   └── cost_service.py       # Cost estimation
│   │
│   ├── middleware/          # Custom middleware
│   │   ├── __init__.py
│   │   └── rate_limit.py    # Rate limiting
│   │
│   └── templates/           # Jinja2 HTML templates
│       ├── base.html        # Layout with ad zones, nav, responsive meta
│       ├── landing.html     # Landing page with sign-in
│       ├── dashboard.html   # User's project list
│       ├── new_project.html # Upload + scenario + style form
│       ├── project_detail.html # Segments, progress, final video
│       └── terms.html       # Terms of Use
│
├── static/                  # CSS, JS, images
│   ├── css/
│   │   └── style.css        # Responsive styles, ad zones
│   ├── js/
│   │   └── app.js           # Upload handling, progress polling
│   └── img/
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Fixtures: test client, test DB, mock services
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_upload_service.py     # Naming convention parsing, validation
│   │   ├── test_moderation_service.py # Content screening logic
│   │   ├── test_cost_service.py       # Cost estimation
│   │   └── test_pipeline_service.py   # Pipeline orchestration logic
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_auth_api.py           # Registration, login, OAuth flow
│   │   ├── test_project_api.py        # Upload, naming, project CRUD
│   │   ├── test_scenario_api.py       # Moderation, splitting
│   │   └── test_generation_api.py     # Pipeline integration
│   └── contract/
│       ├── __init__.py
│       └── test_api_contracts.py      # Schema validation
│
├── uploads/                 # Runtime: user-uploaded photos (gitignored)
├── generated/               # Runtime: generated images, clips, final videos (gitignored)
└── migrations/              # Alembic database migrations
    ├── env.py
    └── versions/
```

**Structure Decision**: Web application (Option 2) selected — FastAPI backend with server-rendered Jinja2 frontend. Single deployable unit. Chosen over SPA (React/Next.js) to minimize complexity and dependency count for MVP, while still supporting responsive design and ad integration.

## Complexity Tracking

> No constitution violations — no justifications needed.
