import hashlib
import json
from typing import Any

from anthropic_api_proxy.schemas.messages import CreateMessageRequest, MessageParam

STOP_REASON_MAPPING = {
    "stop": "end_turn",
    "length": "max_tokens",
    "content_filter": "end_turn",
    "tool_calls": "tool_use",
}


def anthropic_to_openai_req(request: CreateMessageRequest):
    openai_messages = anthropic_to_openai_messages(request)

    openai_tools = anthropic_to_openai_tools(tools=request.tools)

    openai_params: dict[str, Any] = {
        "model": request.model,
        "messages": openai_messages,
        "max_tokens": request.max_tokens,
        "stream": request.stream,
        "extra_body": {"enable_thinking": False}
    }
    if request.thinking is not None and request.thinking.get("type") == "enabled":
        openai_params["extra_body"]["enable_thinking"] = True

    if request.temperature is not None:
        openai_params["temperature"] = request.temperature
    if request.top_p is not None:
        openai_params["top_p"] = request.top_p
    if request.stop_sequences:
        openai_params["stop"] = request.stop_sequences
    if openai_tools:
        openai_params["tools"] = openai_tools

    return openai_params


def anthropic_to_openai_messages(request: CreateMessageRequest) -> \
        list[dict[str, Any]]:
    openai_messages = []
    if request.system is not None:
        system_prompt = []
        if isinstance(request.system, list):
            for msg in request.system:
                system_prompt.append(msg["text"])
        else:
            system_prompt.append(request.system)
        openai_messages.append({"role": "system", "content": "\n".join(system_prompt)})

    for msg in request.messages:
        role = msg.role
        content = msg.content
        if isinstance(content, list):
            text_content = None
            reasoning_content = None
            tool_calls = []

            for content_item in content:
                item_type = content_item.get("type")

                if item_type == "text":
                    text_content = content_item["text"]
                elif item_type == "thinking":
                    reasoning_content = content_item.get("thinking")
                elif item_type == "tool_use":
                    tool_calls.append({
                        "id": content_item["id"],
                        "function": {
                            "arguments": json.dumps(content_item["input"]),
                            "name": content_item["name"],
                        },
                        "type": "function"
                    })
                elif item_type == "tool_result":
                    function_name = content_item["tool_use_id"].split("#")[-1]
                    openai_messages.append({
                        "role": "tool",
                        "name": function_name,
                        "tool_call_id": content_item["tool_use_id"],
                        "content": content_item["content"],
                    })

            if tool_calls:
                openai_messages.append({
                    "role": "assistant",
                    "content": text_content,
                    "reasoning_content": reasoning_content,
                    "tool_calls": tool_calls
                })
            elif text_content is not None or reasoning_content is not None:
                openai_messages.append({
                    "role": role,
                    "content": text_content,
                    "reasoning_content": reasoning_content
                })
        else:
            openai_messages.append({"role": role, "content": content})

    return openai_messages


def anthropic_to_openai_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if not tools:
        return None

    openai_tools = []
    for tool in tools:
        tool_type = tool.get("type")

        if tool_type is not None and tool_type != "custom":
            continue

        openai_tool = {
            "type": "function",
            "function": {
                "name": tool.get("name"),
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {}),
            },
        }
        openai_tools.append(openai_tool)

    return openai_tools if openai_tools else None


def openai_to_anthropic_response(openai_response: Any, model: str) -> dict[str, Any]:
    choice = openai_response.choices[0]
    stop_reason = STOP_REASON_MAPPING.get(choice.finish_reason, "end_turn")
    content = []
    # thinking content should come before text
    if hasattr(choice.message, "reasoning_content") and choice.message.reasoning_content is not None:
        content.append({
            "type": "thinking",
            "thinking": choice.message.reasoning_content,
            "signature": hashlib.sha256(choice.message.reasoning_content.encode("utf-8")).hexdigest()
        })
    if choice.message.content is not None:
        content.append({"text": choice.message.content, "type": "text"})
    if choice.message.tool_calls is not None:
        for tool_call in choice.message.tool_calls:
            content.append({
                "type": "tool_use",
                "id": f"toolu_{tool_call.id}#{tool_call.function.name}",
                "input": json.loads(tool_call.function.arguments),
                "name": tool_call.function.name
            })
    response = {
        "id": f"msg_{openai_response.id}",
        "model": model,
        "role": "assistant",
        "type": "message",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": openai_response.usage.prompt_tokens,
            "output_tokens": openai_response.usage.completion_tokens,
        },
    }

    return response
