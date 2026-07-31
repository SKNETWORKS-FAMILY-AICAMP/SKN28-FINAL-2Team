"""Optional LangSmith tracing helpers for the standalone RAG package."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from typing import Any


TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LangSmithStatus:
    installed: bool
    tracing_requested: bool
    api_key_configured: bool
    enabled: bool
    project: str
    endpoint: str | None
    hide_inputs: bool
    hide_outputs: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def langsmith_status() -> LangSmithStatus:
    """Return a secret-free diagnostic of the current tracing configuration."""

    requested = _env_bool("LANGSMITH_TRACING", False)
    key_configured = bool(os.getenv("LANGSMITH_API_KEY", "").strip())
    try:
        import langsmith  # noqa: F401

        installed = True
        error = None
    except ImportError:
        installed = False
        error = "langsmith package is not installed" if requested else None
    return LangSmithStatus(
        installed=installed,
        tracing_requested=requested,
        api_key_configured=key_configured,
        enabled=installed and requested and key_configured,
        project=os.getenv("LANGSMITH_PROJECT", "skn28-jeju-rag"),
        endpoint=_optional_env("LANGSMITH_ENDPOINT"),
        hide_inputs=_env_bool("LANGSMITH_HIDE_INPUTS", True),
        hide_outputs=_env_bool("LANGSMITH_HIDE_OUTPUTS", True),
        error=error,
    )


def maybe_wrap_openai_client(client: Any) -> Any:
    """Trace direct OpenAI SDK calls when LangSmith is explicitly enabled."""

    status = langsmith_status()
    if not status.enabled or getattr(client, "_skn28_langsmith_wrapped", False):
        return client
    try:
        from langsmith.wrappers import wrap_openai

        wrapped = wrap_openai(client)
        try:
            setattr(wrapped, "_skn28_langsmith_wrapped", True)
        except Exception:
            pass
        return wrapped
    except Exception:
        # Observability must never make the recommendation path unavailable.
        return client


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUE_VALUES


def _optional_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None
