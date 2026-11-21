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
