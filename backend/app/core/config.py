"""App settings, read from environment variables or backend/.env.

Every value has a safe default so the app starts without a .env file.
Secrets are only read here; no endpoint ever returns them.
"""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ folder (this file is backend/app/core/config.py)
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database: falls back to a local SQLite file when DATABASE_URL is empty
    database_url: str = ""

    # LLM
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None

    # Connectors
    jira_base_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None
    slack_bot_token: str | None = None
    telegram_bot_token: str | None = None
    discord_bot_token: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    github_token: str | None = None

    # Auth: secret used to sign JWTs (required for login) and token lifetime
    jwt_secret: str = ""
    jwt_expire_minutes: int = 1440

    # Comma-separated list of frontend URLs allowed to call the API
    cors_origins: str = "http://localhost:3000"

    @field_validator("database_url")
    @classmethod
    def default_to_sqlite(cls, value: str) -> str:
        if value.strip():
            return value.strip()
        return f"sqlite:///{(BACKEND_DIR / 'reqguard.db').as_posix()}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
