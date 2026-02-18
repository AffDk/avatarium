# avatarium Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-07

## Active Technologies
- Python 3.12+ + FastAPI, google-generativeai (Gemini 2.5 Flash), SQLAlchemy 2.0 async, Pydantic v2 (003-person-aware-segments)
- SQLite (aiosqlite) for dev; async SQLAlchemy ORM models (Scenario, Segment, Person) (003-person-aware-segments)

- Python 3.12+ + FastAPI, Uvicorn, Jinja2, python-multipart, google-generativeai, fal-client, ffmpeg-python, python-jose[cryptography], passlib[bcrypt], python-dotenv, SQLAlchemy, aiosqlite, httpx, Authlib (002-avatar-video-pipeline)

## Project Structure

```text
backend/
frontend/
tests/
```

## Commands

cd src; pytest; ruff check .

## Code Style

Python 3.12+: Follow standard conventions

## Recent Changes
- 003-person-aware-segments: Added Python 3.12+ + FastAPI, google-generativeai (Gemini 2.5 Flash), SQLAlchemy 2.0 async, Pydantic v2

- 002-avatar-video-pipeline: Added Python 3.12+ + FastAPI, Uvicorn, Jinja2, python-multipart, google-generativeai, fal-client, ffmpeg-python, python-jose[cryptography], passlib[bcrypt], python-dotenv, SQLAlchemy, aiosqlite, httpx, Authlib

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
