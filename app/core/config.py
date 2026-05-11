import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sabixa API"
    api_prefix: str = "/api/v1"
    database_url: str = ""
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "https://sabixa.vercel.app",
    ]
    groq_api_key: str = ""
    jwt_secret: str = "sabixa-dev-secret-change-me"
    jwt_ttl_minutes: int = 60 * 24 * 7

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SABIXA_")

    @property
    def resolved_groq_api_key(self) -> str:
        return self.groq_api_key or os.getenv("GROQ_API_KEY", "")

    @property
    def resolved_database_url(self) -> str:
        configured_url = (
            self.database_url
            or os.getenv("SABIXA_DATABASE_URL")
            or os.getenv("POSTGRES_URL")
            or os.getenv("DATABASE_URL")
        )
        if configured_url:
            return _normalize_database_url(configured_url)
        if os.getenv("VERCEL") == "1":
            return "sqlite:////tmp/sabixa.db"
        return "sqlite:///./sabixa.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("prisma+postgres://"):
        return database_url.replace("prisma+postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url
