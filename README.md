# Anthropic API Proxy

A FastAPI-based proxy service that translates Anthropic Claude API requests to OpenAI-compatible API format, allowing you to use OpenAI-compatible backends while maintaining Claude API compatibility.

## Features

- **Claude API Compatibility**: Fully compatible with Anthropic's Claude Messages API (`/v1/messages`)
- **OpenAI Backend**: Converts requests to OpenAI-compatible format and forwards to any OpenAI-compatible API endpoint
- **Streaming Support**: Handles both streaming and non-streaming responses with SSE (Server-Sent Events)
- **Extended Thinking Support**: Supports Claude's extended thinking feature with `thinking` parameter
- **Tool Calling**: Translates tool/function calling between Claude and OpenAI formats
- **Model Mapping**: Flexible model mapping configuration to route requests to different backend models
- **Docker Support**: Easy deployment with Docker and Docker Compose

## Architecture

The proxy acts as a middleware that:
1. Accepts Claude API format requests
2. Converts request parameters and message formats to OpenAI-compatible format
3. Forwards to configured OpenAI-compatible backend
4. Converts responses back to Claude API format
5. Returns to the client maintaining Claude API contract

```
Client (Claude API) → Proxy → OpenAI-Compatible Backend
                     ↑
              Format Conversion
```

## Requirements

- Python 3.10+
- FastAPI
- OpenAI Python SDK
- Pydantic

## Installation

### Using UV (Recommended)

```bash
# Clone the repository
git clone https://github.com/fireflyc/anthropic-api-proxy.git
cd anthropic-api-proxy

# Install dependencies with UV
uv venv
uv sync
```

## Configuration

Create a `.env` file in the project root:

```env
API_PROXY_OPEN_AI_URL=https://your-openai-compatible-endpoint.com
API_PROXY_MODEL_MAPPING={"default": "your-default-model", "kimi": "Pro/moonshotai/Kimi-K2.5"}
```

### Configuration Options

- `API_PROXY_OPEN_AI_URL`: The base URL of your OpenAI-compatible API endpoint
- `API_PROXY_MODEL_MAPPING`: JSON object mapping Claude model names to backend model names
  - `default`: The default model to use when no specific mapping is found
  - Add custom mappings for specific model routing

## Usage

### Running Locally

```bash
# Using Python directly
python run.py

# Or using uvicorn
uvicorn anthropic_api_proxy.main:app --host 0.0.0.0 --port 8080
```

The service will start on `http://localhost:8080`.

### Using Docker

```bash
# Build the image
docker build -t anthropic-api-proxy .

# Run the container
docker run -p 8080:8080 --env-file .env anthropic-api-proxy
```

### Making Requests

Use the standard Claude API format:

```bash
curl -X POST http://localhost:8080/v1/messages \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-api-key" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 1024,
    "messages": [
      {
        "role": "user",
        "content": "Hello, Claude!"
      }
    ]
  }'
```

#### Streaming Example

```bash
curl -X POST http://localhost:8080/v1/messages \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-api-key" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 1024,
    "stream": true,
    "messages": [
      {
        "role": "user",
        "content": "Tell me a story"
      }
    ]
  }'
```

#### Extended Thinking Example

```bash
curl -X POST http://localhost:8080/v1/messages \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-api-key" \
  -d '{
    "model": "kimi",
    "max_tokens": 8192,
    "thinking": {"type": "enabled"},
    "messages": [
      {
        "role": "user",
        "content": "Solve this complex problem..."
      }
    ]
  }'
```

#### Tool Calling Example

See `example/message.http` for a complete example with tool definitions.

## API Endpoints

### POST `/v1/messages`

Creates a message using Claude API format.

**Headers:**
- `Content-Type: application/json`
- `X-API-KEY: your-api-key` (required)

**Request Body:**
- `model` (string, required): Model identifier
- `max_tokens` (integer, required): Maximum tokens to generate
- `messages` (array, required): List of conversation messages
- `system` (string|array, optional): System prompt
- `stream` (boolean, optional): Enable streaming responses
- `temperature` (float, optional): Sampling temperature
- `top_p` (float, optional): Nucleus sampling parameter
- `stop_sequences` (array, optional): Sequences where generation should stop
- `tools` (array, optional): Available tools for function calling
- `thinking` (object, optional): Enable extended thinking mode

**Response:**
Returns Claude API compatible response format with message content, usage statistics, and metadata.

## Project Structure

```
anthropic-api-proxy/
├── anthropic_api_proxy/
│   ├── main.py                    # FastAPI application entry point
│   ├── routers/
│   │   └── v1.py                  # API v1 routes
│   ├── services/
│   │   ├── message_service.py     # Message handling logic
│   │   └── conversion_service.py  # Format conversion utilities
│   ├── components/
│   │   ├── claude_headers.py      # Header validation
│   │   ├── openai_client.py       # OpenAI client initialization
│   │   └── stream_adapter.py      # Streaming response adapter
│   ├── schemas/
│   │   └── messages.py            # Pydantic models
│   └── core/
│       ├── config.py              # Configuration management
│       └── logging_config.py      # Logging setup
├── example/
│   └── message.http               # Example requests
├── run.py                         # Application entry point
├── Dockerfile                     # Docker configuration
└── pyproject.toml                 # Project metadata and dependencies
```

## Features in Detail

### Format Conversion

The proxy automatically converts between Claude and OpenAI message formats:

- **System Messages**: Claude's `system` parameter → OpenAI's system message
- **Content Blocks**: Multi-part content (text, thinking, tool_use) → OpenAI format
- **Tool Calls**: Claude tool format → OpenAI function calling format
- **Thinking Content**: Claude's `thinking` type → OpenAI's `reasoning_content`
- **Stop Reasons**: OpenAI finish reasons → Claude stop reasons

### Model Mapping

Configure custom model mappings to route different Claude model requests to different backend models:

```python
MODEL_MAPPING = {
    "default": "Pro/zai-org/GLM-5",
    "kimi": "Pro/moonshotai/Kimi-K2.5",
    "claude-3-5-sonnet-20241022": "gpt-4o"
}
```

### Streaming

Supports Server-Sent Events (SSE) streaming compatible with Claude's streaming format, automatically converting OpenAI stream chunks to Claude event format.

## License

 Apache License Version 2.0

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues, questions, or contributions, please open an issue on GitHub.

## Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [OpenAI Python SDK](https://github.com/openai/openai-python) - OpenAI API client
- [Pydantic](https://docs.pydantic.dev/) - Data validation
- [UV](https://github.com/astral-sh/uv) - Fast Python package installer
