# Research: Avatar Video Generation Pipeline

**Date**: 2026-02-07
**Feature**: 002-avatar-video-pipeline

## Decision 1: Package Manager — uv

**Decision**: Use `uv` for virtual environment management and package installation.

**Rationale**:
- 10–100× faster than pip for dependency resolution and installation
- Built-in virtual environment creation (`uv venv`)
- Lockfile support (`uv.lock`) for reproducible builds
- Native `pyproject.toml` support — no `requirements.txt` needed
- Built-in Python version management (`uv python install 3.12`)
- First-class FastAPI integration documented by Astral

**Alternatives considered**:
- **pip + venv**: Standard but slow, no lockfile, manual `requirements.txt` management
- **Poetry**: Lockfile support but slower resolution, heavier toolchain
- **pipenv**: Slower, less actively developed

**Workflow**:
```bash
# Install uv (one-time)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Initialize project
uv init --name avatarium --python 3.12

# Add dependencies
uv add fastapi uvicorn[standard] jinja2 python-multipart
uv add google-generativeai fal-client ffmpeg-python
uv add sqlalchemy[asyncio] aiosqlite alembic
uv add python-jose[cryptography] passlib[bcrypt] python-dotenv
uv add authlib httpx pydantic-settings slowapi

# Add dev dependencies
uv add --dev pytest pytest-asyncio pytest-cov httpx ruff

# Run the app
uv run uvicorn backend.main:app --reload

# Run tests
uv run pytest
```

## Decision 2: Video Generation Model — LTX Video 13B Distilled

**Decision**: Use `fal-ai/ltx-video-13b-distilled/image-to-video` as the primary video generation model.

**Rationale**:
- **$0.04 flat rate per video clip** — cheapest option available on fal.ai
- Fixed price regardless of clip length (up to the model's default ~5 sec)
- Supports image-to-video with text prompt guidance
- Adequate quality for MVP; can upgrade later

**Alternatives considered**:
- **Wan 2.2 A14B** ($0.20–$0.40 per 5-sec clip at 480p–720p): Better quality but 5–10× more expensive
- **Wan 2.5** ($0.25 per 5-sec clip): Higher quality, 6× cost
- **Kling 2.5 Turbo Pro** ($0.35 per 5-sec clip): Premium quality, 9× cost
- **Veo 3.1** ($0.40/sec = $2.00 per 5-sec clip): Google's best, 50× cost

**Cost per project (LTX)**:
- 5 segments: $0.22 total
- 10 segments: $0.42 total
- 15 segments: $0.62 total

## Decision 3: Image Generation — Qwen Image

**Decision**: Use `fal-ai/qwen-image` for the initial text-to-image generation step.

**Rationale**:
- ~$0.02 per 1 megapixel image — cheapest per-image model on fal.ai
- Good prompt adherence for scene description
- Supports style directives (animation vs. realistic)
- Only called once per project (first segment)

**Alternatives considered**:
- **Flux 2 Flex** (~$0.04/image): Better quality, 2× cost
- **Nano Banana Pro** (~$0.04/image): Google model, similar cost
- **Seedream V4** (~$0.03/image): ByteDance, slightly cheaper alternative

## Decision 4: LLM for Moderation & Splitting — Gemini 2.0 Flash

**Decision**: Use Google Gemini 2.0 Flash via `google-generativeai` Python SDK.

**Rationale**:
- **Free tier**: 15 RPM, 1M tokens/day — sufficient for development and low-volume production
- Paid tier: ~$0.10 per 1M input tokens (negligible cost)
- Can combine moderation and scenario splitting in a single prompt
- Strong content safety filtering built-in
- Python SDK is well-maintained (`google-generativeai` package)

**Alternatives considered**:
- **OpenAI GPT-4o-mini**: ~$0.15/1M input tokens, requires separate API key management
- **Claude Haiku**: ~$0.25/1M tokens, more expensive
- **Local models**: No cost but requires GPU, complex deployment

**Combined prompt strategy**:
```
You are a content moderator and screenplay assistant.
Given the following video scenario, perform TWO tasks:

1. MODERATE: Check if the scenario contains any prohibited content
   (heinous, profane, pornographic, sexual, or violent themes).
   If it does, respond with: {"status": "rejected", "reason": "..."}

2. SPLIT: If approved, split the scenario into segments of approximately
   5 seconds of video content each. Maximum 15 segments.
   Respond with: {"status": "approved", "segments": ["...", "..."]}
```

## Decision 5: Video Concatenation — FFmpeg

**Decision**: Use FFmpeg via `ffmpeg-python` wrapper for server-side video concatenation.

**Rationale**:
- Free, open-source, industry standard
- Handles any input format from fal.ai
- Supports concat demuxer for lossless joining of same-codec clips
- `ffmpeg-python` provides clean Python API
- Can also extract last frame (`-vframes 1`)

**Alternatives considered**:
- **MoviePy**: Higher-level but heavier, slower for simple concatenation
- **OpenCV**: Overkill for concatenation, better for frame extraction
- **Cloud video APIs**: Unnecessary cost for simple join operation

**Last-frame extraction**: `ffmpeg -sseof -0.1 -i clip.mp4 -vframes 1 -q:v 2 last_frame.jpg`

## Decision 6: Web Framework — FastAPI + Jinja2

**Decision**: FastAPI backend with server-rendered Jinja2 templates (no SPA framework).

**Rationale**:
- Single deployable unit — simpler than separate backend + frontend
- Jinja2 templates render responsive HTML with standard CSS
- FastAPI's async support handles concurrent generation pipelines
- Built-in OpenAPI docs for API testing
- Smaller dependency footprint than React/Next.js
- Ad zones are simple HTML divs in the layout template

**Alternatives considered**:
- **Django**: More batteries-included but heavier, less async-native
- **FastAPI + React SPA**: Better UX but doubles complexity, needs Node.js toolchain
- **Flask**: Simpler but lacks async, slower for I/O-heavy pipeline work

## Decision 7: Database — SQLAlchemy Async + SQLite/PostgreSQL

**Decision**: SQLAlchemy 2.0 async with SQLite for development, PostgreSQL for production.

**Rationale**:
- SQLAlchemy 2.0 async works with both SQLite (aiosqlite) and PostgreSQL (asyncpg)
- Zero-config for development (SQLite file)
- Same ORM code works in production with PostgreSQL
- Alembic handles schema migrations
- User data isolation enforced at the query level (all queries include `user_id` filter)

## Decision 8: Authentication — JWT + Google OAuth via Authlib

**Decision**: Email/password with JWT tokens + Google OAuth via Authlib.

**Rationale**:
- `python-jose` for JWT creation/verification
- `passlib` with bcrypt for password hashing
- `Authlib` for Google OAuth flow (well-maintained, supports async)
- Tokens stored in HTTP-only cookies for web security
- Aligns with constitution: email/password + Google OAuth both supported

## Decision 9: FFmpeg Installation for Deployment

**Decision**: Require FFmpeg as a system dependency; document installation in README.

**Rationale**:
- FFmpeg is not a Python package — it must be installed at the OS level
- Docker image will include it (`apt-get install ffmpeg`)
- Development machines need it installed separately
- `ffmpeg-python` is just a wrapper that calls the `ffmpeg` binary

**Installation**:
- Windows: `winget install ffmpeg` or download from https://ffmpeg.org
- macOS: `brew install ffmpeg`
- Linux: `apt-get install ffmpeg`
- Docker: `RUN apt-get update && apt-get install -y ffmpeg`
