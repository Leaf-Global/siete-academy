from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: Literal["development", "staging", "production"] = "development"
    app_secret_key: str = "change-me"
    public_base_url: str = "http://localhost:5173"
    allowed_origins: str = "http://localhost:5173"

    # Accept `X-Dev-User: <email>` and skip Firebase. Off unless a local
    # process opts in. Staging and production refuse to boot if this is true
    # (see the validator below). `app_env` is the environment signal.
    dev_auth_bypass: bool = False

    # When true, Celery runs tasks inline (no broker needed). ONLY for dev.
    celery_always_eager: bool = True

    database_url: str = "postgresql+psycopg://siete:siete@localhost:5432/siete_academy"
    redis_url: str = "redis://localhost:6379/0"

    firebase_credentials_json: str | None = None
    firebase_credentials_path: str | None = None
    firebase_project_id: str | None = None

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-4-7"

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "Siete Academy <noreply@siete.com>"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def dev_auth_bypass_active(self) -> bool:
        """True only when the operator opted in and APP_ENV is development."""
        return self.dev_auth_bypass and self.app_env == "development"

    @model_validator(mode="after")
    def _refuse_dev_auth_bypass_outside_development(self) -> "Settings":
        """Fail fast when the auth bypass is armed outside development.

        APP_ENV is the environment detector (`development`, `staging`,
        `production`). Settings load at import for the API, the Celery
        worker, and Alembic, so a bad combination stops the process before
        it serves traffic or runs migrations. The request path also checks
        `dev_auth_bypass_active`.
        """
        if self.dev_auth_bypass and self.app_env != "development":
            raise ValueError(
                "DEV_AUTH_BYPASS is enabled but APP_ENV is "
                f"{self.app_env!r}. The dev auth bypass is refused outside "
                "development. Set DEV_AUTH_BYPASS=false, or set "
                "APP_ENV=development for local use only."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
