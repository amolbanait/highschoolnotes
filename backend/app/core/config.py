from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HSN_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://hsn:hsn@localhost:5432/hsn"
    storage_dir: str = "./data/files"
    secret_key: str = "dev-only-change-me"
    cookie_secure: bool = False
    session_days: int = 14
    cors_origins: list[str] = ["http://localhost:3000"]

    # Upload and guide limits (design doc: 20 MB, 60 pages or 40,000 words per guide)
    max_upload_bytes: int = 20 * 1024 * 1024
    max_pages: int = 60
    max_words: int = 40_000
    guides_per_hour: int = 10

    # Model settings. Model ids live in config so they can change without code changes.
    anthropic_api_key: str | None = None
    writer_model: str = "claude-opus-5-5"
    plan_effort: str = "high"
    write_effort: str = "medium"
    use_fallbacks: bool = True
    guide_token_budget: int = 600_000
    write_concurrency: int = 4

    # Quality review: a separate, cheaper model scores every section (design doc: below 70 the
    # section is rewritten once with the problems attached, then flagged if still below).
    review_enabled: bool = True
    reviewer_model: str = "claude-sonnet-5-5"
    review_effort: str = "medium"
    quality_threshold: int = 70

    # Worker
    worker_poll_seconds: float = 1.0
    job_lock_seconds: int = 300
    job_max_attempts: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
