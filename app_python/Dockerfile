FROM python:3.14-slim AS builder
# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked


FROM python:3.14-slim
RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /app

# copy virtualenv
COPY --from=builder /app/.venv /app/.venv

# Copy only necessary application files
COPY app.py .

# 🔒 Switch to non-root user
USER appuser

CMD ["/app/.venv/bin/python", "app.py"]
