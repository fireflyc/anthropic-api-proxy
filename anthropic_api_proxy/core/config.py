import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration，environment prefix is API_PROXY_。"""

    OPEN_AI_URL: str
    MODEL_MAPPING: dict[str, str] = {"default": "Pro/zai-org/GLM-5", "kimi":"Pro/moonshotai/Kimi-K2.5"}


@lru_cache
def get_settings() -> Settings:
    env_name = os.environ.get("ENV_NAME")
    print(f"ENV_NAME: {env_name}")
    env_file = ".env"
    if env_name is not None:
        env_file = (".env", f".env.{env_name}")
    Settings.model_config = SettingsConfigDict(env_file=env_file,
                                               env_prefix="API_PROXY_",
                                               case_sensitive=False)
    return Settings()


settings = get_settings()
