FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update -y && apt-get install curl -y

WORKDIR /app
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime

COPY pyproject.toml uv.lock ./
COPY .env /app/

ENV UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    UV_HTTP_TIMEOUT=300 \
    UV_RETRIES=3

RUN uv venv /app/.venv
RUN uv sync

COPY anthropic_api_proxy /app/anthropic_api_proxy

EXPOSE 8080

CMD ["/app/.venv/bin/uvicorn", "anthropic_api_proxy.main:app", "--host", "0.0.0.0", "--port", "8080"]