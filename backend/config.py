"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load all configuration from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ─────────────────────────────────────
    app_env: str = "development"
    app_secret_key: str = "change-me"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # ── Database ────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./avatarium.db"

    # ── fal.ai ──────────────────────────────────
    fal_key: str = ""
    fal_image_model: str = "fal-ai/qwen-image"
    fal_video_model: str = "fal-ai/ltx-video-13b-distilled/image-to-video"

    # ── Gemini ──────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # ── Google OAuth ────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    # ── JWT ──────────────────────────────────────
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # ── Rate Limiting ────────────────────────────
    rate_limit_default: str = "10/minute"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


settings = Settings()
