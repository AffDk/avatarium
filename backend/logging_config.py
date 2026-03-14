"""Per-session file logging configuration.

Each application start creates a new timestamped log file under the
project-root ``logs/`` directory (already in .gitignore).
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

# logs/ lives at the repository root, next to backend/
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"


def setup_logging() -> None:
    """Configure root logger with a per-session file handler + console.

    Call once at application startup.  Subsequent calls are idempotent —
    existing handlers are cleared so the logger is "renewed" each session.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"session_{timestamp}.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── File handler (all levels) ───────────────────────────────────────
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # ── Console handler (INFO and above) ────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # ── Root logger ─────────────────────────────────────────────────────
    root = logging.getLogger()
    # Clear any pre-existing handlers so a restart truly "renews" the logger
    root.handlers.clear()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    root.info("Logging initialised — session log: %s", log_file)

    # ── Suppress noisy third-party loggers ──────────────────────────────
    # httpcore/httpx emit DEBUG lines for every poll request which floods
    # the log when fal.ai queues are long.  SQLAlchemy engine echo is OFF
    # (see database.py) but we also cap the logger here as a safeguard.
    for noisy in (
        "httpcore",
        "httpcore.http11",
        "httpcore.connection",
        "httpx",
        "aiosqlite",
        "sqlalchemy.engine.Engine",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)
