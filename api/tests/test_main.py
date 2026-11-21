import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from formcompiler import main, pipeline, schema
from formcompiler.config import Settings
from formcompiler.report import Report
from formcompiler.upload import FileKind

DOCS = Path(__file__).resolve().parents[2] / "Docs"
PDF_PATH = next(DOCS.glob("3. */*.pdf"))
PDF = PDF_PATH.read_bytes()
SECRET = "sekret-testowy-o-dlugosci-co-najmniej-32-bajtow"
PROBLEM_KEYS = {"type", "title", "status", "detail"}


@pytest.fixture
def configure() -> Iterator[Any]:
    def apply(**env: Any) -> TestClient:
        settings = Settings(_env_file=None, **env)
        main.app.dependency_overrides[main.get_settings] = lambda: settings
        return TestClient(main.app)

    yield apply
    main.app.dependency_overrides.clear()


@pytest.fixture
def client(configure: Any) -> TestClient:
    result: TestClient = configure()
    return result


def upload(client: TestClient, name: str = PDF_PATH.name, data: bytes = PDF, **kw: Any) -> Any:
    return client.post("/api/v1/forms", files={"file": (name, data)}, **kw)


def assert_problem(response: Any, status: int) -> None:
    assert response.status_code == status
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body.keys() >= PROBLEM_KEYS
    assert body["status"] == status


def test_upload_returns_plain_form_json(client: TestClient) -> None:
    response = upload(client)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"title", "tabs", "flow"}
    assert body["tabs"][-1]["type"] == "FINISH"


def test_upload_with_details_returns_form_and_report(client: TestClient) -> None:
    response = upload(client, params={"details": "true"})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"form", "report"}
    assert body["report"]["mode"] == "rules"
    assert set(body["report"]) >= {"mode", "model", "timings_ms", "lint", "fields", "document"}


@pytest.mark.parametrize(
    ("name", "data", "status"),
    [
        ("wniosek;.pdf", PDF, 400),
        ("a" * 247 + ".pdf", PDF, 400),
        ("wniosek.pdf", b"", 400),
        ("wniosek.exe", PDF, 415),
        ("wniosek.png", PDF, 415),
    ],
)
def test_invalid_upload_returns_problem(
    client: TestClient, name: str, data: bytes, status: int
) -> None:
    assert_problem(upload(client, name, data), status)


def test_too_large_upload_returns_413(configure: Any) -> None:
    client = configure(max_upload_mb=1)

    assert_problem(upload(client, data=PDF + bytes(1024 * 1024)), 413)


def test_missing_file_field_returns_400(client: TestClient) -> None:
    response = client.post("/api/v1/forms", files={"dokument": ("a.pdf", PDF)})

    assert_problem(response, 400)


def test_non_multipart_body_returns_415(client: TestClient) -> None:
    response = client.post(
        "/api/v1/forms", content=PDF, headers={"content-type": "application/pdf"}
    )

    assert_problem(response, 415)


def test_unknown_route_and_bad_query_return_problems(client: TestClient) -> None:
    assert_problem(client.get("/nie-ma"), 404)
    assert_problem(upload(client, params={"details": "może"}), 422)


def test_processing_error_returns_500_without_internals(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(data: bytes, kind: FileKind, settings: Settings) -> tuple[schema.Form, Report]:
        raise RuntimeError("wewnętrzny sekret: treść pliku")

    monkeypatch.setattr(pipeline, "process", broken)

    response = upload(client)

    assert_problem(response, 500)
    assert "sekret" not in response.text


def test_processing_over_time_budget_returns_504(
    configure: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = pipeline.process

    def slow(data: bytes, kind: FileKind, settings: Settings) -> tuple[schema.Form, Report]:
        time.sleep(0.5)
        return real(data, kind, settings)

    monkeypatch.setattr(pipeline, "process", slow)
    client = configure(request_timeout_s=0.05)

    assert_problem(upload(client), 504)


def test_health_needs_no_token(configure: Any) -> None:
    client = configure(auth_enabled=True, jwt_algorithms=["HS256"], jwt_secret=SECRET)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "llm_enabled": False}


def test_openapi_docs_describe_the_upload(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()

    body = spec["paths"]["/api/v1/forms"]["post"]["requestBody"]["content"]
    assert "file" in body["multipart/form-data"]["schema"]["properties"]


def token(key: Any = SECRET, algorithm: str = "HS256", **claims: Any) -> str:
    payload = {"sub": "urzednik", "exp": datetime.now(UTC) + timedelta(minutes=5)} | claims
    return jwt.encode(payload, key, algorithm=algorithm)


def bearer(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}


HS256 = {"auth_enabled": True, "jwt_algorithms": ["HS256"], "jwt_secret": SECRET}


def test_valid_token_is_accepted(configure: Any) -> None:
    client = configure(**HS256)

    assert upload(client, headers=bearer(token())).status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        bearer(token(key="inny-sekret-o-dlugosci-co-najmniej-32-bajtow")),
        bearer(token(exp=datetime.now(UTC) - timedelta(minutes=1))),
        bearer(jwt.encode({"sub": "bez-exp"}, SECRET, algorithm="HS256")),
        bearer("to.nie.jest-token"),
    ],
    ids=["missing", "basic", "bad-signature", "expired", "no-exp", "garbage"],
)
def test_bad_or_missing_token_returns_401(configure: Any, headers: dict[str, str]) -> None:
    client = configure(**HS256)

    response = upload(client, headers=headers)

    assert_problem(response, 401)
    assert response.headers["www-authenticate"] == "Bearer"


def test_issuer_and_audience_are_checked(configure: Any) -> None:
    client = configure(**HS256, jwt_issuer="https://login.gov.pl", jwt_audience="biurokratka")
    good = token(iss="https://login.gov.pl", aud="biurokratka")
    wrong = token(iss="https://login.gov.pl", aud="inna-usluga")

    assert upload(client, headers=bearer(good)).status_code == 200
    assert_problem(upload(client, headers=bearer(wrong)), 401)


def test_secret_can_come_from_file(configure: Any, tmp_path: Path) -> None:
    secret_file = tmp_path / "jwt"
    secret_file.write_text(SECRET + "\n", encoding="utf-8")
    client = configure(auth_enabled=True, jwt_algorithms=["HS256"], jwt_secret_file=secret_file)

    assert upload(client, headers=bearer(token())).status_code == 200


def test_rs256_token_is_checked_against_public_key(configure: Any) -> None:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    client = configure(
        auth_enabled=True, jwt_algorithms=["RS256"], jwt_public_key=public_pem.decode()
    )

    assert upload(client, headers=bearer(token(private, "RS256"))).status_code == 200
    # HS256 signed with the public key must not pass (algorithm confusion).
    assert_problem(upload(client, headers=bearer(token(SECRET))), 401)


def test_logs_carry_hash_and_size_but_never_the_file_name(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    name = "Jan Kowalski wniosek poufny.pdf"
    with caplog.at_level("DEBUG"):
        upload(client, name, PDF)
        upload(client, "Jan Kowalski;zle.pdf", PDF)

    assert "sha256=" in caplog.text
    assert f"size={len(PDF)}" in caplog.text
    assert "Kowalski" not in caplog.text
