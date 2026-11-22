FROM python:3.11-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.9.17 /uv /uvx /bin/

WORKDIR /srv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY manger ./manger
RUN uv sync --frozen --no-dev

ENV PATH="/srv/.venv/bin:$PATH"

EXPOSE 8001

CMD ["uvicorn", "manger.entrypoints.fastapi_app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8001"]
