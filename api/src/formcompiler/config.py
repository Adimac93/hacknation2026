"""Runtime settings read from environment variables (and the repo-level .env in development)."""

import ipaddress
from pathlib import Path
from typing import Annotated, Self
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
SYMMETRIC_ALGORITHMS = frozenset({"HS256", "HS384", "HS512"})
ASYMMETRIC_ALGORITHMS = frozenset(
    {"RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512", "EdDSA"}
)


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
    # Decompression-bomb limits, checked before any parser touches the content.
    max_zip_entries: int = 1000
    max_unzipped_mb: int = 200
    max_image_pixels: int = 120_000_000

    auth_enabled: bool = False
    jwt_algorithms: Annotated[list[str], NoDecode] = ["RS256"]
    jwt_secret: SecretStr = SecretStr("")
    jwt_secret_file: Path | None = None
    jwt_public_key: str = ""
    jwt_issuer: str | None = None
    jwt_audience: str | None = None

    tika_url: str = "http://tika:9998"

    llm_enabled: bool = False
    llm_base_url: str = "http://localhost:8080/v1"
    llm_model: str = "mistralai/Ministral-3-8B-Instruct-2512"
    llm_api_key: SecretStr = SecretStr("")
    llm_timeout_s: float = 120.0
    llm_allow_remote: bool = False

    @field_validator("jwt_secret_file", "jwt_issuer", "jwt_audience", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("jwt_algorithms", mode="before")
    @classmethod
    def _split_algorithms(cls, value: object) -> object:
        if isinstance(value, str):
            return [a.strip() for a in value.split(",") if a.strip()]
        return value

    @model_validator(mode="after")
    def _auth_has_matching_key(self) -> Self:
        if not self.auth_enabled:
            return self
        algorithms = set(self.jwt_algorithms)
        if not algorithms or not algorithms <= SYMMETRIC_ALGORITHMS | ASYMMETRIC_ALGORITHMS:
            raise ValueError(f"JWT_ALGORITHMS has unsupported values: {sorted(algorithms)}")
        # Mixing families lets an attacker sign HS* tokens with the public key.
        if algorithms & SYMMETRIC_ALGORITHMS and algorithms & ASYMMETRIC_ALGORITHMS:
            raise ValueError("JWT_ALGORITHMS must not mix HMAC and public-key algorithms")
        if algorithms <= SYMMETRIC_ALGORITHMS:
            has_secret = bool(self.jwt_secret.get_secret_value())
            if has_secret == (self.jwt_secret_file is not None):
                raise ValueError("set exactly one of JWT_SECRET and JWT_SECRET_FILE")
        elif not self.jwt_public_key:
            raise ValueError("JWT_PUBLIC_KEY is required for public-key JWT algorithms")
        return self

    @model_validator(mode="after")
    def _remote_llm_needs_explicit_opt_in(self) -> Self:
        host = urlsplit(self.llm_base_url).hostname or ""
        if not self.llm_allow_remote and not is_local_host(host):
            raise ValueError(
                f"LLM_BASE_URL points to a remote host ({host}); "
                "set LLM_ALLOW_REMOTE=true to allow it"
            )
        return self
