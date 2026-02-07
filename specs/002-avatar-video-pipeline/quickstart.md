# Quickstart Guide: Avatarium

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.12+ | `python --version` |
| uv | latest | `uv --version` |
| FFmpeg | 6.x+ | `ffmpeg -version` |
| Git | any | `git --version` |

### Install uv (if not installed)

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install FFmpeg (if not installed)

```powershell
# Windows (via winget)
winget install --id Gyan.FFmpeg

# macOS (via Homebrew)
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

---

## 1. Clone & Enter Repository

```bash
git clone <your-repo-url> avatarium
cd avatarium
```

## 2. Create Virtual Environment & Install Dependencies

```bash
# Initialize the project (creates pyproject.toml if not present)
uv init --python 3.12

# Create venv and install all dependencies
uv sync
```

If starting fresh from the planned `pyproject.toml`:

```bash
# Add production dependencies
uv add fastapi uvicorn[standard] jinja2 python-multipart
uv add sqlalchemy[asyncio] aiosqlite asyncpg alembic
uv add fal-client google-generativeai
uv add ffmpeg-python
uv add authlib python-jose[cryptography] passlib[bcrypt] httpx
uv add python-dotenv pydantic pydantic-settings

# Add dev dependencies
uv add --dev pytest pytest-asyncio pytest-cov httpx
uv add --dev ruff mypy
```

## 3. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env
```

Edit `.env` with your values:

```ini
# ── App ─────────────────────────────────────────
APP_ENV=development
APP_SECRET_KEY=<generate-with: python -c "import secrets; print(secrets.token_hex(32))">
APP_HOST=0.0.0.0
APP_PORT=8000

# ── Database ────────────────────────────────────
DATABASE_URL=sqlite+aiosqlite:///./avatarium.db

# ── fal.ai ──────────────────────────────────────
FAL_KEY=<your-fal-api-key>

# ── Gemini ──────────────────────────────────────
GEMINI_API_KEY=<your-gemini-api-key>

# ── Google OAuth (optional) ─────────────────────
GOOGLE_CLIENT_ID=<your-google-client-id>
GOOGLE_CLIENT_SECRET=<your-google-client-secret>
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback

# ── JWT ─────────────────────────────────────────
JWT_SECRET_KEY=<generate-with: python -c "import secrets; print(secrets.token_hex(32))">
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60
```

## 4. Initialize Database

```bash
# Run Alembic migrations
uv run alembic upgrade head
```

## 5. Run Development Server

```bash
uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Visit: **http://localhost:8000**

API docs: **http://localhost:8000/docs** (Swagger UI)

## 6. Run Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=backend --cov-report=term-missing

# Run specific test module
uv run pytest tests/unit/test_services_pipeline.py -v
```

## 7. Lint & Type Check

```bash
# Lint
uv run ruff check .

# Auto-fix lint issues
uv run ruff check --fix .

# Format
uv run ruff format .

# Type check
uv run mypy backend/
```

---

## API Keys Setup

### fal.ai

1. Go to https://fal.ai/dashboard/keys
2. Create a new API key
3. Set `FAL_KEY` in `.env`

### Google Gemini

1. Go to https://aistudio.google.com/apikey
2. Create a new API key
3. Set `GEMINI_API_KEY` in `.env`

### Google OAuth (optional)

1. Go to https://console.cloud.google.com/apis/credentials
2. Create an OAuth 2.0 Client ID (Web application)
3. Add `http://localhost:8000/api/auth/google/callback` as authorized redirect URI
4. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`

---

## Common Issues

| Issue | Solution |
|-------|----------|
| `ffmpeg not found` | Install FFmpeg and ensure it's on PATH |
| `fal_client` timeout | Check FAL_KEY is valid; fal.ai may have queue delays |
| `GOOGLE_CLIENT_ID not set` | Google OAuth is optional; email/password auth works without it |
| Database locked (SQLite) | Only one writer at a time in dev; use PostgreSQL for prod |
