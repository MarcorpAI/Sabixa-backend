import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sabixa API"
    api_prefix: str = "/api/v1"
    database_url: str = ""
    cors_origins: list[str] = ["*"]
    groq_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SABIXA_")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        if os.getenv("VERCEL") == "1":
            return "sqlite:////tmp/sabixa.db"
        return "sqlite:///./sabixa.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
