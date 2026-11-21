"""FastAPI application: form upload, health check and OpenAPI docs."""

import asyncio
import hashlib
import logging
import traceback
from collections.abc import Mapping
from functools import lru_cache
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.exceptions import HTTPException

from formcompiler import pipeline, schema
from formcompiler.auth import AuthError, verify
from formcompiler.config import Settings
from formcompiler.report import Report
from formcompiler.upload import UploadError, read_upload, validate

PROBLEM_JSON = "application/problem+json"
HTTP_TITLES = {404: "Nie znaleziono", 405: "Niedozwolona metoda"}

logger = logging.getLogger("formcompiler")
if not logger.handlers:
    # uvicorn configures only its own loggers; give ours the same shape on stderr.
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

app = FastAPI(
    title="Biurokratka",
    summary="Blankiet formularza urzędowego -> JSON konfiguracji formularza COI",
    version="0.1.0",
)


@lru_cache
def get_settings() -> Settings:
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]
bearer = HTTPBearer(auto_error=False)


def problem(
    status: int, title: str, detail: str, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    """RFC 9457 problem details."""
    body = {"type": "about:blank", "title": title, "status": status, "detail": detail}
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def require_token(
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)],
) -> None:
    verify(credentials.credentials if credentials else None, settings)


@app.exception_handler(UploadError)
async def upload_error(request: Request, exc: UploadError) -> JSONResponse:
    return problem(exc.status, exc.title, exc.detail)


@app.exception_handler(AuthError)
async def auth_error(request: Request, exc: AuthError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"}
    return problem(401, "Brak autoryzacji", exc.detail, headers)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    title = HTTP_TITLES.get(exc.status_code, HTTPStatus(exc.status_code).phrase)
    return problem(exc.status_code, title, str(exc.detail), exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    names = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})
    return problem(422, "Nieprawidłowe parametry żądania", "Popraw: " + ", ".join(names))


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    log_failure("request", exc)
    return internal_error()


def internal_error() -> JSONResponse:
    return problem(500, "Błąd wewnętrzny", "Nie udało się przetworzyć żądania.")


def log_failure(digest: str, exc: BaseException) -> None:
    """Log the error type and where it was raised, never its message: it may quote the file."""
    frames = traceback.extract_tb(exc.__traceback__)
    where = f"{frames[-1].filename}:{frames[-1].lineno}" if frames else "?"
    logger.error("failed sha256=%s error=%s at %s", digest, type(exc).__name__, where)


def run(filename: str, data: bytes, settings: Settings) -> tuple[schema.Form, Report]:
    return pipeline.process(data, validate(filename, data, settings), settings)


UPLOAD_BODY: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["file"],
                    "properties": {"file": {"type": "string", "format": "binary"}},
                }
            }
        },
    }
}
PROBLEM_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"description": description, "content": {PROBLEM_JSON: {}}}
    for status, description in [
        (400, "Zła nazwa pliku albo uszkodzone żądanie"),
        (401, "Brak lub zły token"),
        (413, "Plik za duży"),
        (415, "Nieobsługiwany typ albo treść niezgodna z rozszerzeniem"),
        (500, "Błąd wewnętrzny"),
        (504, "Przekroczony limit czasu"),
    ]
}


@app.post(
    "/api/v1/forms",
    dependencies=[Depends(require_token)],
    openapi_extra=UPLOAD_BODY,
    responses=PROBLEM_RESPONSES,
)
async def create_form(
    request: Request, settings: SettingsDep, details: bool = False
) -> JSONResponse:
    """Turn one form blank into the form JSON; `details=true` adds the processing report."""
    filename, data = await read_upload(
        request.headers.get("content-type"),
        request.headers.get("content-length"),
        request.stream(),
        settings,
    )
    digest = hashlib.sha256(data).hexdigest()
    logger.info("upload sha256=%s size=%d", digest, len(data))
    try:
        async with asyncio.timeout(settings.request_timeout_s):
            form, report = await asyncio.to_thread(run, filename, data, settings)
    except UploadError as exc:
        logger.info("rejected sha256=%s status=%d", digest, exc.status)
        raise
    except TimeoutError:
        logger.warning("timeout sha256=%s after %ss", digest, settings.request_timeout_s)
        return problem(504, "Przekroczony limit czasu", "Przetwarzanie pliku trwało zbyt długo.")
    except Exception as exc:
        log_failure(digest, exc)
        return internal_error()
    logger.info("done sha256=%s mode=%s", digest, report.mode)
    if details:
        return JSONResponse({"form": form.dump(), "report": report.model_dump(mode="json")})
    return JSONResponse(form.dump())


@app.get("/health")
def health(settings: SettingsDep) -> dict[str, Any]:
    return {"status": "ok", "llm_enabled": settings.llm_enabled}
