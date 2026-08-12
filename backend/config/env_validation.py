from __future__ import annotations

import re
from collections.abc import Mapping

from django.core.exceptions import ImproperlyConfigured


_REQUIRED = (
    "DJANGO_SECRET_KEY",
    "ALLOWED_HOSTS",
    "CORS_ALLOWED_ORIGINS",
    "CSRF_TRUSTED_ORIGINS",
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "ACCOUNT_DB_NAME",
    "TRAVEL_DB_NAME",
    "MYSQL_DATABASE",
    "OPENAI_API_KEY",
    "CHROMA_MODE",
)
_DATABASE_NAME = re.compile(r"^[A-Za-z0-9_]+$")


def validate_production_environment(environ: Mapping[str, str]) -> None:
    """Fail before startup when production configuration is incomplete or unsafe."""

    missing = [name for name in _REQUIRED if not environ.get(name, "").strip()]
    if missing:
        raise ImproperlyConfigured(
            "Missing production environment variables: " + ", ".join(missing)
        )

    if environ["TRAVEL_DB_NAME"] != environ["MYSQL_DATABASE"]:
        raise ImproperlyConfigured(
            "TRAVEL_DB_NAME and MYSQL_DATABASE must identify the same shared catalog DB"
        )

    for name in ("ACCOUNT_DB_NAME", "TRAVEL_DB_NAME", "MYSQL_DATABASE"):
        if not _DATABASE_NAME.fullmatch(environ[name]):
            raise ImproperlyConfigured(
                f"{name} may contain only letters, numbers, and underscores"
            )

    _validate_port(environ, "MYSQL_PORT")

    allowed_hosts = _csv(environ["ALLOWED_HOSTS"])
    if "*" in allowed_hosts:
        raise ImproperlyConfigured("ALLOWED_HOSTS must not contain '*' in production")
    if any("://" in host for host in allowed_hosts):
        raise ImproperlyConfigured("ALLOWED_HOSTS entries must not include a URL scheme")

    for name in ("CORS_ALLOWED_ORIGINS", "CSRF_TRUSTED_ORIGINS"):
        invalid = [origin for origin in _csv(environ[name]) if not origin.startswith("https://")]
        if invalid:
            raise ImproperlyConfigured(f"{name} must contain only https:// origins")

    for name in ("SECURE_SSL_REDIRECT", "SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE"):
        value = environ.get(name)
        if value is not None and value.strip().lower() not in {"1", "true", "yes", "on"}:
            raise ImproperlyConfigured(f"{name} must not be disabled in production")

    chroma_mode = environ["CHROMA_MODE"].strip().lower()
    if chroma_mode != "http":
        raise ImproperlyConfigured("CHROMA_MODE must be 'http' in production")
    if not environ.get("CHROMA_HOST", "").strip():
        raise ImproperlyConfigured("CHROMA_HOST is required when CHROMA_MODE=http")
    _validate_port(environ, "CHROMA_PORT")


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _validate_port(environ: Mapping[str, str], name: str) -> None:
    try:
        port = int(environ.get(name, ""))
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ImproperlyConfigured(f"{name} must be between 1 and 65535")
