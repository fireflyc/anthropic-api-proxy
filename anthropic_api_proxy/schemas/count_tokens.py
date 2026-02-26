from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from anthropic_api_proxy.schemas.messages import MessageParam


class CountTokensRequest(BaseModel):

    model_config = ConfigDict(extra="allow")

    messages: list[MessageParam] = Field(..., description="List of input messages")
    model: str = Field(..., description="Model ID")
    system: str | list[dict[str, Any]] | None = None
    tools: list[dict[str, Any]] | None = None
    thinking: dict[str, Any] | None = None
    output_config: dict[str, Any] | None = None


class CountTokensResponse(BaseModel):

    input_tokens: int = Field(..., description="total number of input tokens")
