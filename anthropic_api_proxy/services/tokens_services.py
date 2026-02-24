from openai import OpenAI

from anthropic_api_proxy.schemas.count_tokens import CountTokensRequest, CountTokensResponse
from anthropic_api_proxy.schemas.messages import CreateMessageRequest
from anthropic_api_proxy.services.message_service import create_message_sync


async def count_message_tokens(request: CountTokensRequest, client: OpenAI, api_key: str) -> CountTokensResponse:
    message_request = CreateMessageRequest(messages=request.messages,
                                           model=request.model,
                                           system=request.system,
                                           tools=request.tools,
                                           thinking=request.thinking,
                                           max_tokens=64000)
    response = await create_message_sync(request=message_request, client=client, api_key=api_key)
    count_resp = CountTokensResponse(input_tokens=response.get("usage").get("input_tokens"))
    return count_resp