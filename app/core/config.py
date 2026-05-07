from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sabixa API"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./sabixa.db"
    cors_origins: list[str] = ["*"]
    groq_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SABIXA_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
