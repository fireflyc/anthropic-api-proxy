import json
import logging
import uuid
from typing import AsyncGenerator, Any

from openai import AsyncOpenAI, OpenAI, APIStatusError

from anthropic_api_proxy.components.stream_adapter import StreamAdapter
from anthropic_api_proxy.schemas.messages import CreateMessageRequest
from anthropic_api_proxy.services.conversion_service import (
    openai_to_anthropic_response, anthropic_to_openai_req
)
from anthropic_api_proxy.services.trace_service import trace_log_request, trace_log_response, StreamResponseAccumulator

LOGGER = logging.getLogger(__name__)


async def create_message_sync(request: CreateMessageRequest, client: OpenAI, api_key: str) -> dict[str, Any]:
    openai_params = anthropic_to_openai_req(request=request)
    openai_params["stream"] = False

    original_api_key = client.api_key
    client.api_key = api_key

    try:
        request_id = f"req-{uuid.uuid4()}"
        trace_log_request(request_id, openai_params)
        openai_response = client.chat.completions.create(**openai_params)
        trace_log_response(request_id, openai_response.model_dump())
        anthropic_response = openai_to_anthropic_response(openai_response=openai_response, model=request.model)
        return anthropic_response
    except APIStatusError as e:
        LOGGER.exception(f"APIStatusError in create_message_sync")
        return {
            "id": "msg_1",
            "model": request.model,
            "role": "assistant",
            "type": "message",
            "content": f"模型出错了，HTTP 返回{e.status_code}",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
            },
        }
    finally:
        client.api_key = original_api_key


async def create_message_stream(request: CreateMessageRequest, async_client: AsyncOpenAI, api_key: str) -> \
        AsyncGenerator[str, None]:
    openai_params = anthropic_to_openai_req(request=request)
    openai_params["stream"] = True
    openai_params["stream_options"] = {"include_usage": True}

    original_api_key = async_client.api_key
    async_client.api_key = api_key
    stream_adapter = StreamAdapter(request.model)

    request_id = f"req-{uuid.uuid4()}"
    # Create accumulator for streaming response logging
    accumulator = StreamResponseAccumulator(request_id)

    try:
        trace_log_request(request_id, openai_params)
        stream = await async_client.chat.completions.create(**openai_params)

        yield stream_adapter.first_event()
        async for chunk in stream:
            # Accumulate chunk for logging
            accumulator.process_chunk(chunk)
            
            new_chunk = stream_adapter.convert_chunk(chunk)
            if new_chunk is None:
                continue
            
            for event in new_chunk:
                event_str = f"event: {event["type"]}\ndata: {json.dumps(event)}\n\n"
                yield event_str

        yield stream_adapter.block_close()
        yield stream_adapter.message_stop_delta()
        yield stream_adapter.message_final()
        
        # Log accumulated OpenAI response
        accumulator.log_accumulated_response()
        
    except APIStatusError as e:
        LOGGER.exception(f"APIStatusError in create_message_stream")
        yield stream_adapter.first_event()
        yield stream_adapter.message_final()
    finally:
        async_client.api_key = original_api_key
