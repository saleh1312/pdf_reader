FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-writer \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.17 /uv /uvx /bin/

WORKDIR /srv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY worker.py parse_images.py to_images.py ./

ENV PATH="/srv/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

CMD ["python", "worker.py"]
