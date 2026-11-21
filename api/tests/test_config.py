from typing import Any

import pytest
from pydantic import ValidationError

from formcompiler.config import Settings


def make(**env: Any) -> Settings:
    # _env_file=None keeps a developer's local .env out of the tests.
    return Settings(_env_file=None, **env)


def test_defaults_run_in_rules_mode_against_local_server() -> None:
    settings = make()

    assert settings.llm_enabled is False
    assert settings.llm_allow_remote is False
    assert settings.llm_base_url == "http://localhost:8080/v1"


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8080/v1",
        "http://127.0.0.1:8080/v1",
        "http://host.docker.internal:8080/v1",
        "http://llm:8080/v1",
        "http://172.16.0.62:8080/v1",
        "http://192.168.1.10:8080/v1",
    ],
)
def test_local_and_private_model_urls_are_accepted(url: str) -> None:
    assert make(llm_base_url=url).llm_base_url == url


def test_remote_model_url_is_rejected_without_explicit_flag() -> None:
    with pytest.raises(ValidationError, match="LLM_ALLOW_REMOTE"):
        make(llm_base_url="https://api.eu.edenai.run/v3")


def test_remote_model_url_is_accepted_with_explicit_flag() -> None:
    settings = make(llm_base_url="https://api.eu.edenai.run/v3", llm_allow_remote=True)

    assert settings.llm_base_url == "https://api.eu.edenai.run/v3"


def test_settings_are_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("LLM_MODEL", "mistral/ministral-8b-2512@eu")
    monkeypatch.setenv("MAX_UPLOAD_MB", "5")

    settings = make()

    assert settings.llm_enabled is True
    assert settings.llm_model == "mistral/ministral-8b-2512@eu"
    assert settings.max_upload_mb == 5


def test_api_key_is_not_shown_in_repr() -> None:
    settings = make(llm_api_key="sekret-123")

    assert "sekret-123" not in repr(settings)
    assert settings.llm_api_key.get_secret_value() == "sekret-123"


def test_auth_is_off_by_default_and_needs_no_key() -> None:
    settings = make()

    assert settings.auth_enabled is False
    assert settings.jwt_algorithms == ["RS256"]


def test_jwt_algorithms_are_read_as_comma_separated_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_ALGORITHMS", "RS256, ES256")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "-----BEGIN PUBLIC KEY-----")

    assert make().jwt_algorithms == ["RS256", "ES256"]


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"jwt_algorithms": ["HS256"]}, "exactly one"),
        ({"jwt_algorithms": ["HS256"], "jwt_secret": "a", "jwt_secret_file": "/s"}, "exactly one"),
        ({"jwt_algorithms": ["RS256"]}, "JWT_PUBLIC_KEY"),
        ({"jwt_algorithms": ["HS256", "RS256"], "jwt_secret": "a"}, "must not mix"),
        ({"jwt_algorithms": ["none"]}, "unsupported"),
        ({"jwt_algorithms": []}, "unsupported"),
    ],
)
def test_enabled_auth_rejects_unsafe_key_setup(env: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        make(auth_enabled=True, **env)


@pytest.mark.parametrize(
    "env",
    [
        {"jwt_algorithms": ["HS256"], "jwt_secret": "sekret"},
        {"jwt_algorithms": ["HS256"], "jwt_secret_file": "/run/secrets/jwt"},
        {"jwt_algorithms": ["RS256"], "jwt_public_key": "-----BEGIN PUBLIC KEY-----"},
    ],
)
def test_enabled_auth_accepts_complete_key_setup(env: dict[str, Any]) -> None:
    assert make(auth_enabled=True, **env).auth_enabled is True


def test_jwt_secret_is_not_shown_in_repr() -> None:
    settings = make(auth_enabled=True, jwt_algorithms=["HS256"], jwt_secret="tajne-456")

    assert "tajne-456" not in repr(settings)


def test_blank_optional_jwt_values_from_env_file_are_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_FILE", "")
    monkeypatch.setenv("JWT_ISSUER", "")
    monkeypatch.setenv("JWT_AUDIENCE", "")

    settings = make()

    assert (settings.jwt_secret_file, settings.jwt_issuer, settings.jwt_audience) == (None,) * 3
