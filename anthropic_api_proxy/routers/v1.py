"""V1 routes compatible with Claude API: messages, count_tokens, models."""
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from anthropic_api_proxy.components.claude_headers import ClaudeHeaders, require_claude_headers
from anthropic_api_proxy.components.openai_client import get_async_openai_client, get_openai_client
from anthropic_api_proxy.core.config import settings
from anthropic_api_proxy.schemas.count_tokens import CountTokensRequest, CountTokensResponse
from anthropic_api_proxy.schemas.messages import CreateMessageRequest
from anthropic_api_proxy.services.message_service import create_message_stream, create_message_sync
from anthropic_api_proxy.services.tokens_services import count_message_tokens

router = APIRouter()

LOGGER = logging.getLogger(__name__)


def get_model_name(model_name: str):
    if model_name.startswith("c-"):
        return model_name[2:]
    else:
        for original_name, mapping_name in settings.MODEL_MAPPING.items():
            if original_name in model_name.lower():
                return mapping_name
        return settings.MODEL_MAPPING.get("default")


@router.post("/messages", response_model=None)
async def create_message(request: CreateMessageRequest, headers: ClaudeHeaders = Depends(require_claude_headers)) -> \
        dict[str, Any] | StreamingResponse:
    """Create a message, compatible with Claude POST /v1/messages. Returns SSE streaming response when stream=true, otherwise returns complete JSON."""

    request.model = get_model_name(request.model)
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


@router.post("/messages/count_tokens", response_model=CountTokensResponse)
async def count_tokens(request: CountTokensRequest,
                       headers: ClaudeHeaders = Depends(require_claude_headers)) -> CountTokensResponse:
    request.model = get_model_name(request.model)
    client = get_openai_client()
    return await count_message_tokens(request=request, client=client, api_key=headers.x_api_key)
