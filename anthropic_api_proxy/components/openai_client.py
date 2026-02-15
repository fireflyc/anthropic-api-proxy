from functools import lru_cache

from openai import AsyncOpenAI, OpenAI

from anthropic_api_proxy.core.config import settings


@lru_cache
def get_openai_client() -> OpenAI:
    return OpenAI(base_url=settings.OPEN_AI_URL, api_key="dummy-key")


@lru_cache
def get_async_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(base_url=settings.OPEN_AI_URL, api_key="dummy-key")
