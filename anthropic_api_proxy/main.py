"""FastAPI application entry point, mounts v1 routes compatible with Claude API."""
import logging

from fastapi import FastAPI

from anthropic_api_proxy.core.logging_config import setup_logging
from anthropic_api_proxy.routers import v1
setup_logging()

LOGGER = logging.getLogger(__name__)

app = FastAPI(title="Anthropic API Proxy", description="Proxy service compatible with Claude API")
app.include_router(v1.router, prefix="/v1", tags=["v1"])
