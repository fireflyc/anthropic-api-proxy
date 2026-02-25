import logging
from typing import Any
from copy import deepcopy

from anthropic_api_proxy.core.logging_config import REQUEST_RESPONSE_LOGGER

REQUEST_RESPONSE_LOG = logging.getLogger(REQUEST_RESPONSE_LOGGER)


def trace_log_request(params: dict[str, Any], include_tools: bool = True) -> None:
    """
    Log request parameters.
    
    Args:
        params: The request parameters to log
        include_tools: Whether to include tools in the log (default: True)
    """
    if not include_tools:
        # Create a copy to avoid modifying the original
        params_copy = deepcopy(params)
        # Remove tools if present
        if "tools" in params_copy:
            params_copy["tools"] = f"<{len(params_copy['tools'])} tools omitted>"
    else:
        params_copy = params
    
    REQUEST_RESPONSE_LOG.info(f"Request params: {params_copy}")


def trace_log_response(response: Any) -> None:
    """
    Log response data.
    
    Args:
        response: The response data to log
    """
    REQUEST_RESPONSE_LOG.info(f"Response: {response}")


class StreamResponseAccumulator:
    """Accumulator for OpenAI streaming responses."""
    
    def __init__(self):
        self.accumulated_content = ""
        self.accumulated_role = None
        self.accumulated_tool_calls = []
        self.finish_reason = None
        self.usage_info = None
    
    def process_chunk(self, chunk: Any) -> None:
        """
        Process a single OpenAI streaming chunk and accumulate its data.
        
        Args:
            chunk: OpenAI streaming chunk
        """
        # Accumulate delta content from OpenAI chunks
        if chunk.choices and len(chunk.choices) > 0:
            choice = chunk.choices[0]
            delta = choice.delta
            
            if delta.role:
                self.accumulated_role = delta.role
            if delta.content:
                self.accumulated_content += delta.content
            if delta.tool_calls:
                # Accumulate tool calls
                for tool_call in delta.tool_calls:
                    # Extend or create tool call entries
                    if tool_call.index is not None:
                        while len(self.accumulated_tool_calls) <= tool_call.index:
                            self.accumulated_tool_calls.append({
                                "id": "", 
                                "type": "", 
                                "function": {"name": "", "arguments": ""}
                            })
                        if tool_call.id:
                            self.accumulated_tool_calls[tool_call.index]["id"] = tool_call.id
                        if tool_call.type:
                            self.accumulated_tool_calls[tool_call.index]["type"] = tool_call.type
                        if tool_call.function:
                            if tool_call.function.name:
                                self.accumulated_tool_calls[tool_call.index]["function"]["name"] = tool_call.function.name
                            if tool_call.function.arguments:
                                self.accumulated_tool_calls[tool_call.index]["function"]["arguments"] += tool_call.function.arguments
            
            if choice.finish_reason:
                self.finish_reason = choice.finish_reason
        
        # Check for usage info (usually in the last chunk)
        if hasattr(chunk, 'usage') and chunk.usage:
            self.usage_info = chunk.usage
    
    def get_accumulated_response(self) -> dict[str, Any]:
        """
        Get the accumulated response in a structured format.
        
        Returns:
            Dictionary containing the accumulated response data
        """
        return {
            "role": self.accumulated_role,
            "content": self.accumulated_content,
            "tool_calls": self.accumulated_tool_calls if self.accumulated_tool_calls else None,
            "finish_reason": self.finish_reason,
            "usage": self.usage_info.model_dump() if self.usage_info else None
        }
    
    def log_accumulated_response(self) -> None:
        """Log the accumulated streaming response."""
        accumulated_response = self.get_accumulated_response()
        trace_log_response(accumulated_response)
