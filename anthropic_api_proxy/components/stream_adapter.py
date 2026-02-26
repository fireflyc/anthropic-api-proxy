import hashlib
import json
import logging
import uuid
from enum import Enum, auto
from io import StringIO
from typing import Optional, List, Dict, Any

from openai.types.chat.chat_completion_chunk import ChoiceDelta, ChatCompletionChunk

from anthropic_api_proxy.services.conversion_service import STOP_REASON_MAPPING

LOGGER = logging.getLogger(__name__)

# Constants
TOOL_ID_PREFIX = "toolu_"
DEFAULT_STOP_REASON = "end_turn"


class ContentMode(Enum):
    """Content block mode enumeration"""
    TOOLS = auto()
    THINKING = auto()
    CONTENT = auto()


class BlockState:
    """Manages the state of a single content block"""

    def __init__(self, index: int, mode: ContentMode, tool_info: Optional[Dict[str, str]] = None):
        self.index = index
        self.mode = mode
        self.tool_info = tool_info
        self.reasoning_buffer = StringIO()

    def build_start_event(self) -> Dict[str, Any]:
        """Build content_block_start event based on the block mode"""
        content_block = self._create_content_block()
        return {
            "type": "content_block_start",
            "index": self.index,
            "content_block": content_block
        }

    def _create_content_block(self) -> Dict[str, Any]:
        """Create the appropriate content block structure based on mode"""
        if self.mode == ContentMode.TOOLS:
            return {
                "type": "tool_use",
                "name": self.tool_info["name"],
                "id": f"{TOOL_ID_PREFIX}{self.tool_info['id']}#{self.tool_info['name']}",
                "input": {}
            }
        elif self.mode == ContentMode.THINKING:
            return {"type": "thinking", "thinking": ""}
        else:
            return {"type": "text", "text": ""}

    def build_delta_event(self, content: str) -> Dict[str, Any]:
        """Build content_block_delta event based on the block mode"""
        delta = self._create_delta(content)
        return {
            "type": "content_block_delta",
            "index": self.index,
            "delta": delta
        }

    def _create_delta(self, content: str) -> Dict[str, str]:
        """Create the appropriate delta structure based on mode"""
        if self.mode == ContentMode.TOOLS:
            return {"type": "input_json_delta", "partial_json": content}
        elif self.mode == ContentMode.THINKING:
            return {"type": "thinking_delta", "thinking": content}
        else:
            return {"type": "text_delta", "text": content}

    def build_signature_event(self) -> Dict[str, Any]:
        """Build signature event for thinking block"""
        thinking_content = self.reasoning_buffer.getvalue()
        signature = hashlib.sha256(thinking_content.encode("utf-8")).hexdigest()
        
        return {
            "type": "content_block_delta",
            "index": self.index,
            "delta": {
                "type": "signature_delta",
                "signature": signature
            }
        }

    def build_stop_event(self) -> Dict[str, Any]:
        """Build content_block_stop event"""
        return {"type": "content_block_stop", "index": self.index}


class StreamAdapter:
    """Adapter for converting OpenAI streaming response to Anthropic format"""

    def __init__(self, model_id: str):
        self.model_id = model_id
        self._current_block: Optional[BlockState] = None
        self._block_index = 0
        self._awaiting_first_block = True
        self._stop_reason = DEFAULT_STOP_REASON
        self._output_tokens = 0
        self._input_tokens = 0
        self._current_tool_index: Optional[int] = None

    def _detect_mode(self, delta: ChoiceDelta) -> Optional[ContentMode]:
        """Detect the content mode from the delta object"""
        if delta.tool_calls is not None:
            return ContentMode.TOOLS
        if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
            return ContentMode.THINKING
        if delta.content is not None:
            return ContentMode.CONTENT
        return None

    def _create_block(self, mode: ContentMode, delta: ChoiceDelta) -> BlockState:
        """Create a new content block with the appropriate mode and metadata"""
        tool_info = None
        if mode == ContentMode.TOOLS:
            tool_call = delta.tool_calls[0]
            tool_info = {
                "name": tool_call.function.name,
                "id": tool_call.id
            }
        return BlockState(self._block_index, mode, tool_info)

    def _has_mode_changed(self, new_mode: ContentMode, delta: ChoiceDelta) -> bool:
        """Check if content mode or tool index has changed, requiring a new block"""
        if self._current_block is None:
            return False
        
        # Check if mode changed
        if self._current_block.mode != new_mode:
            return True
        
        # For tool calls, check if the tool index changed (multiple tool calls)
        if new_mode == ContentMode.TOOLS and delta.tool_calls:
            current_tool_index = delta.tool_calls[0].index
            if self._current_tool_index is not None and current_tool_index != self._current_tool_index:
                return True
        
        return False

    def _is_empty_delta(self, delta: ChoiceDelta) -> bool:
        """Check if the delta contains no meaningful content"""
        has_tool_calls = delta.tool_calls is not None
        has_content = delta.content is not None and delta.content != ""
        has_reasoning = hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None
        
        return not (has_tool_calls or has_content or has_reasoning)

    def first_event(self) -> str:
        """Generate message_start event with initial message structure"""
        msg_id = uuid.uuid4().hex
        event = {
            "type": "message_start",
            "message": {
                "id": msg_id,
                "type": "message",
                "role": "assistant",
                "content": [],  # Empty list - content blocks will be added via delta events
                "model": self.model_id,
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0}
            }
        }
        return f"event: message_start\ndata: {json.dumps(event)}\n\n"

    def convert_chunk(self, chunk: ChatCompletionChunk) -> Optional[List[Dict[str, Any]]]:
        """
        Convert a single OpenAI chunk to Anthropic event format

        Returns:
            List of events to emit, or None if the chunk should be skipped
        """
        # Update tokens from usage (handles the final chunk with usage but empty choices)
        if chunk.usage is not None:
            self._input_tokens = chunk.usage.prompt_tokens
            self._output_tokens = chunk.usage.completion_tokens

        # Handle final chunk with usage but empty choices array
        if len(chunk.choices) == 0:
            return None

        choice = chunk.choices[0]

        if choice.finish_reason is not None:
            self._stop_reason = STOP_REASON_MAPPING.get(
                choice.finish_reason, self._stop_reason
            )

        delta = choice.delta

        # Skip chunks with no meaningful content
        if self._is_empty_delta(delta):
            return None

        return self._process_delta(delta)

    def _process_delta(self, delta: ChoiceDelta) -> List[Dict[str, Any]]:
        """
        Process a delta object and generate appropriate Anthropic events
        
        Returns:
            List of events representing content block changes
        """
        events = []
        new_mode = self._detect_mode(delta)

        if new_mode is None:
            LOGGER.error(f"Received unknown delta: {delta}")
            raise RuntimeError("Unknown delta response")

        # Handle mode/tool switching (requires closing current block and opening new one)
        if self._has_mode_changed(new_mode, delta):
            events.extend(self._close_current_block_with_signature())
            events.extend(self._open_new_block(new_mode, delta))
        # Handle first block initialization
        elif self._awaiting_first_block:
            events.extend(self._open_new_block(new_mode, delta))
            self._awaiting_first_block = False

        # Process the delta content
        content = self._extract_delta_content(delta, new_mode)
        self._accumulate_thinking_content(new_mode, content)
        events.append(self._current_block.build_delta_event(content))

        return events

    def _close_current_block_with_signature(self) -> List[Dict[str, Any]]:
        """Close the current block, adding signature event if it's a thinking block"""
        events = []
        
        # Add signature for thinking blocks before closing
        if self._current_block.mode == ContentMode.THINKING:
            events.append(self._current_block.build_signature_event())
        
        events.append(self._current_block.build_stop_event())
        return events

    def _open_new_block(self, mode: ContentMode, delta: ChoiceDelta) -> List[Dict[str, Any]]:
        """Create and open a new content block"""
        if not self._awaiting_first_block:
            self._block_index += 1
        
        self._current_block = self._create_block(mode, delta)
        
        # Track tool index for detecting tool changes
        if mode == ContentMode.TOOLS and delta.tool_calls:
            self._current_tool_index = delta.tool_calls[0].index
        
        return [self._current_block.build_start_event()]

    def _accumulate_thinking_content(self, mode: ContentMode, content: str) -> None:
        """Accumulate thinking content for signature generation"""
        if mode == ContentMode.THINKING:
            self._current_block.reasoning_buffer.write(content)

    def _extract_delta_content(self, delta: ChoiceDelta, mode: ContentMode) -> str:
        """Extract the appropriate content from delta based on mode"""
        if mode == ContentMode.TOOLS:
            return delta.tool_calls[0].function.arguments
        elif mode == ContentMode.THINKING:
            return delta.reasoning_content
        else:
            return delta.content

    def block_close(self) -> str:
        """Generate event to close the current content block"""
        if self._current_block:
            event = self._current_block.build_stop_event()
            return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
        return ""

    def message_stop_delta(self) -> str:
        """Generate message_delta event with stop reason and token usage"""
        event = {
            "type": "message_delta",
            "delta": {"stop_reason": self._stop_reason, "stop_sequence": None},
            "usage": {"output_tokens": self._output_tokens, "input_tokens": self._input_tokens}
        }
        return f"event: message_delta\ndata: {json.dumps(event)}\n\n"

    def message_final(self) -> str:
        """Generate message_stop event to signal end of stream"""
        event = {"type": "message_stop"}
        return f"event: message_stop\ndata: {json.dumps(event)}\n\n"
