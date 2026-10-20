from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_secret_key: str = "dev-secret-key-change-me"
    app_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:3000"

    database_url: str = "postgresql+asyncpg://goflow:goflow@localhost:5432/goflow"
    redis_url: str = "redis://localhost:6379/0"

    token_encryption_key: str = ""

    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_graph_api_version: str = "v21.0"

    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""

    session_cookie_secure: bool = False
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
