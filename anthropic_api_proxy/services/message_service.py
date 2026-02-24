import json
import logging
from typing import AsyncGenerator, Any

from openai import AsyncOpenAI, OpenAI

from anthropic_api_proxy.components.stream_adapter import StreamAdapter
from anthropic_api_proxy.core.logging_config import REQUEST_RESPONSE_LOGGER
from anthropic_api_proxy.schemas.messages import CreateMessageRequest
from anthropic_api_proxy.services.conversion_service import (
    openai_to_anthropic_response, anthropic_to_openai_req
)

LOGGER = logging.getLogger(__name__)
REQUEST_RESPONSE_LOG = logging.getLogger(REQUEST_RESPONSE_LOGGER)

async def create_message_sync(request: CreateMessageRequest, client: OpenAI, api_key: str) -> dict[str, Any]:
    openai_params = anthropic_to_openai_req(request=request)
    openai_params["stream"] = False

    original_api_key = client.api_key
    client.api_key = api_key

    try:
        REQUEST_RESPONSE_LOG.info(f"Request params: {openai_params}")
        openai_response = client.chat.completions.create(**openai_params)
        anthropic_response = openai_to_anthropic_response(openai_response=openai_response, model=request.model)
        REQUEST_RESPONSE_LOG.info(f"Response: {anthropic_response}")
        return anthropic_response
    finally:
        client.api_key = original_api_key


async def create_message_stream(request: CreateMessageRequest, async_client: AsyncOpenAI, api_key: str) -> \
        AsyncGenerator[str, None]:
    openai_params = anthropic_to_openai_req(request=request)
    openai_params["stream"] = True

    original_api_key = async_client.api_key
    async_client.api_key = api_key
    try:
        REQUEST_RESPONSE_LOG.info(f"Streaming request params: {openai_params}")
        stream = await async_client.chat.completions.create(**openai_params)
        stream_adapter = StreamAdapter(request.model)

        yield stream_adapter.first_event()
        async for chunk in stream:
            new_chunk = stream_adapter.convert_chunk(chunk)
            REQUEST_RESPONSE_LOG.info(f"Streaming chunk: {chunk} -> {new_chunk}")
            if new_chunk is None:
                continue
            for event in new_chunk:
                event_str = f"event: {event["type"]}\ndata: {json.dumps(event)}\n\n"
                yield event_str

        yield stream_adapter.block_close()
        yield stream_adapter.message_stop_delta()
        REQUEST_RESPONSE_LOG.info(f"Streaming response completed")
        yield stream_adapter.message_final()
    finally:
        async_client.api_key = original_api_key
