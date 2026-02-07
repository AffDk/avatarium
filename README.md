# Avatarium

AI-powered avatar video generation platform. Upload photos of people, write a scenario, and get a stylized video — animated or cinematic — generated entirely by AI.

## Features

- **Email/password & Google OAuth** authentication
- **Photo upload** with automatic person detection from filenames (`alice_1.jpg`, `alice_2.png`)
- **AI content moderation** via Google Gemini 2.0 Flash
- **Scenario splitting** into ~5-second segments
- **Iterative video generation** via fal.ai (LTX Video 13B Distilled)
- **Automatic video concatenation** via FFmpeg
- **Two video styles**: Animation ("Cartoonic") and Cinematic ("Movie-like")
- **Responsive design** — works on desktop, tablet, and mobile
- **Privacy-first** — strict per-user data isolation

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12+ |
| Package Manager | [uv](https://docs.astral.sh/uv/) |
| Web Framework | FastAPI + Jinja2 (server-rendered) |
| Database | SQLite (dev) / PostgreSQL (prod) via SQLAlchemy async |
| Video Generation | [fal.ai](https://fal.ai) — LTX Video 13B Distilled |
| Image Generation | [fal.ai](https://fal.ai) — Qwen Image |
| Moderation & Splitting | Google Gemini 2.0 Flash |
| Video Processing | FFmpeg via ffmpeg-python |
| Auth | JWT + bcrypt (email/password), Authlib (Google OAuth) |

## Prerequisites

- **Python 3.12+**
- **uv** — [install instructions](https://docs.astral.sh/uv/getting-started/installation/)
- **FFmpeg 6.x+** — must be on system PATH
- **Git**

## Quick Start

```bash
# Clone the repository
git clone <your-repo-url> avatarium
cd avatarium

# Install dependencies
uv sync

# Copy environment config
cp .env.example .env
# Edit .env with your API keys (see below)

# Run database migrations
uv run alembic upgrade head

# Start development server
uv run uvicorn backend.main:app --reload --port 8000
```

Open **http://localhost:8000** in your browser.

## Environment Variables

Create a `.env` file at the project root (see `.env.example`):

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_SECRET_KEY` | Yes | App-wide secret for session security |
| `DATABASE_URL` | Yes | SQLAlchemy connection string |
| `FAL_KEY` | Yes | fal.ai API key ([get one](https://fal.ai/dashboard/keys)) |
| `GEMINI_API_KEY` | Yes | Google Gemini API key ([get one](https://aistudio.google.com/apikey)) |
| `JWT_SECRET_KEY` | Yes | Secret for signing JWT tokens |
| `GOOGLE_CLIENT_ID` | No | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | No | Google OAuth client secret |

## Development

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=backend --cov-report=term-missing

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run mypy backend/
```

## Project Structure

```
avatarium/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Pydantic settings
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── api/                 # Route handlers
│   ├── services/            # Business logic (pipeline, moderation, etc.)
│   ├── middleware/          # Auth, CORS, rate limiting
│   └── templates/           # Jinja2 HTML templates
├── static/                  # CSS, JS, images
├── tests/                   # pytest test suite
├── migrations/              # Alembic database migrations
├── uploads/                 # User-uploaded photos (gitignored)
├── generated/               # Generated videos and images (gitignored)
├── pyproject.toml           # Project config & dependencies
└── .env                     # Environment variables (gitignored)
```

## Cost Estimate

Per video project (5–15 segments):

| Component | Cost |
|-----------|------|
| Image generation (Qwen) | ~$0.02/image |
| Video generation (LTX Video) | $0.04/clip |
| Moderation (Gemini Flash) | Free tier |
| Concatenation (FFmpeg) | $0.00 |
| **Total (5 segments)** | **~$0.22** |
| **Total (15 segments)** | **~$0.62** |

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.
