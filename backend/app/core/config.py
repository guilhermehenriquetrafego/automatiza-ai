"""
AUTOMATIZA AI — Configuration
Central configuration loaded from environment variables.
All hosting is free-tier compatible (Supabase, Upstash, Cloudflare R2, Vercel, Render).
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "AUTOMATIZA AI"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"  # development | staging | production
    API_PREFIX: str = "/api/v1"

    # --- Database (Supabase free tier) ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/automatiza"

    # --- Redis (Upstash free tier) ---
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # --- OpenAI ---
    OPENAI_API_KEY: str = ""
    OPENAI_TEXT_MODEL: str = "gpt-4o"
    OPENAI_IMAGE_MODEL: str = "gpt-image-2"  # ChatGPT Images 2.0

    # --- Cloudflare R2 (free tier — 10GB storage, free egress) ---
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "automatiza-ai"
    R2_ENDPOINT_URL: str = ""
    R2_PUBLIC_URL: str = ""

    # --- CDP Automation ---
    CDP_DEBUG: bool = False
    CDP_HEADLESS: bool = True  # Set to False for debugging
    CDP_NAVIGATION_TIMEOUT: int = 30000  # ms
    CDP_ACTION_DELAY_MIN: float = 0.5  # seconds — min delay between actions
    CDP_ACTION_DELAY_MAX: float = 2.5  # seconds — max delay between actions
    CDP_MOUSE_STEPS: int = 25  # steps for Bezier mouse movement
    CDP_SESSION_TIMEOUT: int = 1800  # 30 min max session
    CDP_MAX_CONCURRENT_SESSIONS: int = 5  # max parallel browser sessions

    # --- Motor de Exposição ---
    EXPOSURE_RECRAWL_INTERVAL_MIN: int = 30  # re-check OLX limits every 30 min
    EXPOSURE_SIMILARITY_THRESHOLD: float = 0.60  # max trigram similarity between variations
    EXPOSURE_MAX_DAILY_BURST: float = 1.5  # max % of daily quota in a single burst
    EXPOSURE_WEEKEND_WEIGHT: float = 1.3  # weight multiplier for weekends
    EXPOSURE_DEFAULT_PEAK_HOURS: list[int] = [9, 13, 18, 20]  # default peak posting hours

    # --- Security ---
    SECRET_KEY: str = "dev-secret-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALGORITHM: str = "HS256"

    # --- CORS ---
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://automatiza-ai.vercel.app",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
