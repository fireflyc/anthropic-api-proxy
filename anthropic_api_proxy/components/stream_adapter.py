import hashlib
import json
import logging
import uuid
from enum import Enum, auto
from io import StringIO
from typing import Optional

from openai.types.chat.chat_completion_chunk import ChoiceDelta, ChatCompletionChunk

from anthropic_api_proxy.services.conversion_service import STOP_REASON_MAPPING

LOGGER = logging.getLogger(__name__)


class ContentMode(Enum):
    """Content block mode enumeration"""
    TOOLS = auto()
    THINKING = auto()
    CONTENT = auto()


class BlockState:
    """Manages the state of a single content block"""

    def __init__(self, index: int, mode: ContentMode, tool_info: Optional[dict] = None):
        self.index = index
        self.mode = mode
        self.tool_info = tool_info
        self.reasoning_buffer = StringIO()

    def build_start_event(self) -> dict:
        """Build content_block_start event"""
        if self.mode == ContentMode.TOOLS:
            return {
                "type": "content_block_start",
                "index": self.index,
                "content_block": {
                    "type": "tool_use",
                    "name": self.tool_info["name"],
                    "id": f"toolu_{self.tool_info['id']}_{self.tool_info['name']}",
                    "input": {}
                }
            }
        elif self.mode == ContentMode.THINKING:
            return {
                "type": "content_block_start",
                "index": self.index,
                "content_block": {"type": "thinking", "thinking": ""}
            }
        else:
            return {
                "type": "content_block_start",
                "index": self.index,
                "content_block": {"type": "text", "text": ""}
            }

    def build_delta_event(self, content: str) -> dict:
        """Build content_block_delta event"""
        if self.mode == ContentMode.TOOLS:
            return {
                "type": "content_block_delta",
                "index": self.index,
                "delta": {"type": "input_json_delta", "partial_json": content}
            }
        elif self.mode == ContentMode.THINKING:
            return {
                "type": "content_block_delta",
                "index": self.index,
                "delta": {"type": "thinking_delta", "thinking": content}
            }
        else:
            return {
                "type": "content_block_delta",
                "index": self.index,
                "delta": {"type": "text_delta", "text": content}
            }

    def build_signature_event(self) -> dict:
        """Build signature event for thinking block"""
        return {
            "type": "content_block_delta",
            "index": self.index,
            "delta": {
                "type": "signature_delta",
                "signature": hashlib.sha256(
                    self.reasoning_buffer.getvalue().encode("utf-8")
                ).hexdigest()
            }
        }

    def build_stop_event(self) -> dict:
        """Build content_block_stop event"""
        return {"type": "content_block_stop", "index": self.index}


class StreamAdapter:
    """Adapter for converting OpenAI streaming response to Anthropic format"""

    def __init__(self, model_id: str):
        self.model_id = model_id
        self._current_block: Optional[BlockState] = None
        self._block_index = 0
        self._is_first_block = True
        self._stop_reason = "end_turn"
        self._output_tokens = 0
        self._input_tokens = 0

    def _detect_mode(self, delta: ChoiceDelta) -> Optional[ContentMode]:
        """Detect the mode of the delta"""
        if delta.tool_calls is not None:
            return ContentMode.TOOLS
        if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
            return ContentMode.THINKING
        if delta.content is not None:
            return ContentMode.CONTENT
        return None

    def _create_block(self, mode: ContentMode, delta: ChoiceDelta) -> BlockState:
        """Create a new content block"""
        tool_info = None
        if mode == ContentMode.TOOLS:
            tool_info = {
                "name": delta.tool_calls[0].function.name,
                "id": delta.tool_calls[0].id
            }
        return BlockState(self._block_index, mode, tool_info)

    def _is_mode_changed(self, new_mode: ContentMode) -> bool:
        """Check if the mode has changed"""
        return self._current_block is not None and self._current_block.mode != new_mode

    def first_event(self) -> str:
        """Generate message_start event"""
        msg_id = uuid.uuid4().hex
        event = {
            "type": "message_start",
            "message": {
                "id": msg_id,
                "type": "message",
                "role": "assistant",
                "content": "",
                "model": self.model_id,
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0}
            }
        }
        return f"event: message_start\ndata: {json.dumps(event)}\n\n"

    def convert_chunk(self, chunk: ChatCompletionChunk):
        """Convert a single chunk"""
        choice = chunk.choices[0]
        self._input_tokens += chunk.usage.prompt_tokens
        self._output_tokens += chunk.usage.completion_tokens

        if choice.finish_reason is not None:
            self._stop_reason = STOP_REASON_MAPPING.get(
                choice.finish_reason, self._stop_reason
            )

        delta = choice.delta

        # Skip invalid packets
        if delta.tool_calls is None and \
           (delta.content is None or delta.content == "") and \
           (not hasattr(delta, 'reasoning_content') or delta.reasoning_content is None):
            return None

        return self._process_delta(delta)

    def _process_delta(self, delta: ChoiceDelta):
        """Process delta and generate event list"""
        events = []
        new_mode = self._detect_mode(delta)

        if new_mode is None:
            LOGGER.error(f"Received unknown delta: {delta}")
            raise RuntimeError("Unknown delta response")

        # Handle mode switching
        if self._is_mode_changed(new_mode):
            # Add signature when thinking block ends
            if self._current_block.mode == ContentMode.THINKING:
                events.append(self._current_block.build_signature_event())

            # Close current block
            events.append(self._current_block.build_stop_event())

            # Create new block
            self._block_index += 1
            self._current_block = self._create_block(new_mode, delta)
            events.append(self._current_block.build_start_event())

        # Handle first block
        elif self._is_first_block:
            self._current_block = self._create_block(new_mode, delta)
            events.append(self._current_block.build_start_event())
            self._is_first_block = False

        # Accumulate thinking content
        content = self._get_content(delta, new_mode)
        if new_mode == ContentMode.THINKING:
            self._current_block.reasoning_buffer.write(content)

        # Add delta event
        events.append(self._current_block.build_delta_event(content))

        return events

    def _get_content(self, delta: ChoiceDelta, mode: ContentMode) -> str:
        """Extract content from delta"""
        if mode == ContentMode.TOOLS:
            return delta.tool_calls[0].function.arguments
        elif mode == ContentMode.THINKING:
            return delta.reasoning_content
        else:
            return delta.content

    def block_close(self) -> str:
        """Close the current content block"""
        if self._current_block:
            event = self._current_block.build_stop_event()
            return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
        return ""

    def message_stop_delta(self) -> str:
        """Generate message_delta event"""
        event = {
            "type": "message_delta",
            "delta": {"stop_reason": self._stop_reason, "stop_sequence": None},
            "usage": {"output_tokens": self._output_tokens, "input_tokens": self._input_tokens}
        }
        return f"event: message_delta\ndata: {json.dumps(event)}\n\n"

    def message_final(self) -> str:
        """Generate message_stop event"""
        event = {"type": "message_stop"}
        return f"event: message_stop\ndata: {json.dumps(event)}\n\n"
