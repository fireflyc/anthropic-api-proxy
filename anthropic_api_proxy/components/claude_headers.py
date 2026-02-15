
from fastapi import Header, HTTPException, Request

CONTENT_TYPE_JSON = "application/json"


def require_claude_headers(
    request: Request,
    authorization: str | None = Header(None, alias="Authorization", description="API Key (Bearer token)"),
    x_api_key: str | None = Header(None, alias="x-api-key", description="API Key"),
    anthropic_version: str | None = Header(None, alias="anthropic-version", description="API Version, 2023-06-01"),
    content_type: str | None = Header(None, alias="content-type"),
) -> "ClaudeHeaders":
    api_key = x_api_key
    if not api_key:
        if authorization:
            # Remove "Bearer " prefix
            api_key = authorization.replace("Bearer ", "").strip()
    
    if not api_key or not api_key.strip():
        raise HTTPException(status_code=401, detail="Missing or empty x-api-key or Authorization header")
    if not anthropic_version:
        anthropic_version = "2023-06-01"
    if request.method == "POST":
        if not content_type or not content_type.strip().lower().startswith(CONTENT_TYPE_JSON):
            raise HTTPException(
                status_code=400,
                detail="POST request must include content-type: application/json",
            )
    return ClaudeHeaders(x_api_key=api_key.strip(), anthropic_version=anthropic_version.strip())


class ClaudeHeaders:
    def __init__(self, x_api_key: str, anthropic_version: str) -> None:
        self.x_api_key = x_api_key
        self.anthropic_version = anthropic_version
