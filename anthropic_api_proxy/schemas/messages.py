"""Request and response models for Messages API (compatible with Claude POST /v1/messages)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageParam(BaseModel):
    """Single conversation message, compatible with Claude API MessageParam."""

    model_config = ConfigDict(extra="allow")

    role: str = Field(..., description="user or assistant")
    content: str | list[dict[str, Any]] = Field(..., description="Text or array of content blocks")


class CreateMessageRequest(BaseModel):
    """POST /v1/messages request body, compatible with Claude Messages API."""

    model_config = ConfigDict(extra="allow")

    model: str = Field(..., description="Model ID")
    max_tokens: int = Field(..., description="Maximum number of tokens to generate")
    messages: list[MessageParam] = Field(..., description="List of input messages")
    system: str | list[dict[str, Any]] | None = None
    stream: bool | None = None
    temperature: float | None = None
    stop_sequences: list[str] | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: dict[str, Any] | None = None
    thinking: dict[str, Any] | None = None
    top_k: int | None = None
    top_p: float | None = None
