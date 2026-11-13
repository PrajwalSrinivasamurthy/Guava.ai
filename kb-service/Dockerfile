FROM python:3.14-slim

ENV UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN pip install --no-cache-dir uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY kb_service ./kb_service

RUN useradd --system --no-create-home app
USER app

EXPOSE 8120
CMD ["uvicorn", "--factory", "kb_service.server:create", "--host", "0.0.0.0", "--port", "8120"]
