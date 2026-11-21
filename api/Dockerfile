# syntax=docker/dockerfile:1
# API service (FastAPI + formcompiler). Slim (glibc) rather than Alpine: onnxruntime has no musl
# wheels (D10). Everything is pinned; nothing is downloaded while serving requests.

ARG PYTHON_IMAGE=python:3.14.10-slim-trixie

FROM ghcr.io/astral-sh/uv:0.8.20 AS uv

# --- build: virtual environment from uv.lock -----------------------------------------------------
FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.14 \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
# Dependencies first, so that a code change does not invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# RapidOCR weights (PP-OCRv6 small, D5) go here; the ingest track adds them. Download them at
# build time from a pinned URL, verified against a hard-coded SHA-256, e.g.:
#   ADD --checksum=sha256:<sum> <det-model-url> /models/rapidocr/det.onnx
# then copy /models into the runtime stage (COPY --from=build) and point RapidOCR at it.
# Nothing is downloaded at runtime.

# --- runtime -------------------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime

# Fallback OCR, Tesseract 5 with `pol` data (D5): the ingest track adds the system packages:
#   RUN apt-get update \
#    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-pol \
#    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --home-dir /nonexistent \
      --shell /usr/sbin/nologin app

COPY --from=build /app/.venv /app/.venv

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
USER app:app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

CMD ["uvicorn", "formcompiler.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
