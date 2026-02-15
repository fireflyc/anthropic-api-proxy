"""V1 routes compatible with Claude API: messages, count_tokens, models."""
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from anthropic_api_proxy.components.claude_headers import ClaudeHeaders, require_claude_headers
from anthropic_api_proxy.components.openai_client import get_async_openai_client, get_openai_client
from anthropic_api_proxy.core.config import settings
from anthropic_api_proxy.schemas.messages import CreateMessageRequest
from anthropic_api_proxy.services.message_service import create_message_stream, create_message_sync

router = APIRouter()

LOGGER = logging.getLogger(__name__)


@router.post("/messages", response_model=None)
async def create_message(request: CreateMessageRequest, headers: ClaudeHeaders = Depends(require_claude_headers)) -> \
        dict[str, Any] | StreamingResponse:
    """Create a message, compatible with Claude POST /v1/messages. Returns SSE streaming response when stream=true, otherwise returns complete JSON."""
    request.model = settings.MODEL_MAPPING.get(request.model,
                                               settings.MODEL_MAPPING.get("default"))

    LOGGER.info(f"===Request===\n{request.model_dump()}\n===Request===\n")
    if request.stream:
        # Streaming response - use async client
        async_client = get_async_openai_client()
        return StreamingResponse(
            create_message_stream(request=request, async_client=async_client, api_key=headers.x_api_key),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable Nginx buffering
            },
        )
    else:
        # Synchronous response - use sync client
        client = get_openai_client()
        return await create_message_sync(request=request, client=client, api_key=headers.x_api_key)
