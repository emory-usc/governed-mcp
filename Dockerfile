# syntax=docker/dockerfile:1

# ---- build stage ------------------------------------------------------------
FROM python:3.14-slim AS builder
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --extra mcp

# ---- runtime stage: slim, non-root -----------------------------------------
FROM python:3.14-slim AS runtime
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN groupadd -r app && useradd -r -g app app
COPY --from=builder /app /app
USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import socket,sys; s=socket.socket(); s.settimeout(3); sys.exit(0 if s.connect_ex(('127.0.0.1',8000))==0 else 1)"]

CMD ["governed", "run", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
