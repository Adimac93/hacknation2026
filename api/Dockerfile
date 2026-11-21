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

# The rapidocr wheel bundles the same weights; drop them so OCR_MODEL_DIR is the only source.
RUN rm -f /app/.venv/lib/python3.14/site-packages/rapidocr/models/*.onnx

# --- OCR weights ---------------------------------------------------------------------------------
# PP-OCRv6 small (D5, Apache-2.0) from the RapidOCR 3.10.0 model repository, verified against the
# SHA-256 that rapidocr 3.10.0 lists in its default_models.yaml. Nothing is downloaded at runtime.
FROM scratch AS ocr-models
ARG OCR_MODELS_URL=https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0/onnx/PP-OCRv6
ADD --chmod=644 --checksum=sha256:090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f \
    ${OCR_MODELS_URL}/det/PP-OCRv6_det_small.onnx /rapidocr/PP-OCRv6_det_small.onnx
ADD --chmod=644 --checksum=sha256:6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884 \
    ${OCR_MODELS_URL}/rec/PP-OCRv6_rec_small.onnx /rapidocr/PP-OCRv6_rec_small.onnx

# --- runtime -------------------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime

# Fallback OCR, Tesseract 5 with `pol` data (D5, Apache-2.0); versions follow the pinned base image.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-pol \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --home-dir /nonexistent \
      --shell /usr/sbin/nologin app

COPY --from=build /app/.venv /app/.venv
COPY --from=ocr-models /rapidocr /opt/models/rapidocr

ENV PATH=/app/.venv/bin:$PATH \
    OCR_MODEL_DIR=/opt/models/rapidocr \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
USER app:app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

CMD ["uvicorn", "formcompiler.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
