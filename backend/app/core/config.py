from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[3] / ".env",
                                      env_prefix="APP_", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite:///./application.db"
    auth_mode: str = "development"
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    cors_origins: str = "http://localhost:5173"
    nlp_mode: str = "mock"
    nlp_base_url: str | None = None
    nlp_api_token: str | None = None
    nlp_timeout_seconds: float = 15
    max_text_chars: int = 10000
    max_audio_bytes: int = 15_000_000
    audio_storage_dir: str = "./private-audio"
    upload_expiry_minutes: int = 10
    retention_days: int = 365
    rate_limit_per_minute: int = 30
    worker_poll_seconds: float = 2
    development_staff_subjects: str = "local-staff"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
