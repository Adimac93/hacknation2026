"""Runtime settings read from environment variables (and the repo-level .env in development)."""

import ipaddress
from pathlib import Path
from typing import Self
from urllib.parse import urlsplit

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


def is_local_host(host: str) -> bool:
    """True for loopback, private networks and single-label or internal Docker hostnames."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host == "localhost" or "." not in host or host.endswith((".internal", ".local"))
    return address.is_loopback or address.is_private


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ENV_FILE, extra="ignore")

    max_upload_mb: int = 20
    max_pages: int = 30
    request_timeout_s: float = 300.0

    tika_url: str = "http://tika:9998"

    llm_enabled: bool = False
    llm_base_url: str = "http://localhost:8080/v1"
    llm_model: str = "mistralai/Ministral-3-8B-Instruct-2512"
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_s: float = 120.0
    llm_allow_remote: bool = False

    @model_validator(mode="after")
    def _remote_llm_needs_explicit_opt_in(self) -> Self:
        host = urlsplit(self.llm_base_url).hostname or ""
        if not self.llm_allow_remote and not is_local_host(host):
            raise ValueError(
                f"LLM_BASE_URL points to a remote host ({host}); "
                "set LLM_ALLOW_REMOTE=true to allow it"
            )
        return self
