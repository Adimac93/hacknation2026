"""Bearer JWT check for the API, active only when AUTH_ENABLED=true."""

from typing import Any

import jwt

from formcompiler.config import SYMMETRIC_ALGORITHMS, Settings


class AuthError(Exception):
    """Missing or invalid token; `detail` is shown to the user."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def verification_key(settings: Settings) -> str:
    """HMAC secret (inline or from a mounted secret file) or the PEM public key."""
    if not set(settings.jwt_algorithms) <= SYMMETRIC_ALGORITHMS:
        return settings.jwt_public_key
    if settings.jwt_secret_file is not None:
        return settings.jwt_secret_file.read_text(encoding="utf-8").strip()
    return settings.jwt_secret.get_secret_value()


def verify(token: str | None, settings: Settings) -> dict[str, Any] | None:
    """Return the claims of a Bearer token, or None when authentication is off."""
    if not settings.auth_enabled:
        return None
    if not token:
        raise AuthError("Wymagany token Bearer w nagłówku Authorization.")
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            verification_key(settings),
            algorithms=settings.jwt_algorithms,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["exp"]},
        )
    except jwt.ExpiredSignatureError:
        raise AuthError("Token wygasł.") from None
    except jwt.InvalidTokenError:
        raise AuthError("Token jest nieprawidłowy.") from None
    return claims
