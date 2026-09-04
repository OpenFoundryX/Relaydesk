FROM ghcr.io/astral-sh/uv:0.9.26 AS uv

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY --from=uv /uv /uvx /bin/
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn relaydesk.main:app --host 0.0.0.0 --port 8000 --reload"]
