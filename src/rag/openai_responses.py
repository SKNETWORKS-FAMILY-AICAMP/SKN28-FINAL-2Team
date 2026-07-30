"""Small resilience helpers for OpenAI Responses API calls."""

from __future__ import annotations

import os
from typing import Any, Mapping, Sequence

from .llm import LLMError


def reasoning_options(model: str, *, evaluation: bool = False) -> dict[str, Any]:
    """Return GPT-5 reasoning controls without affecting other model families."""

    if not str(model).lower().startswith("gpt-5"):
        return {}
    env_name = (
        "OPENAI_EVAL_REASONING_EFFORT"
        if evaluation
        else "OPENAI_REASONING_EFFORT"
    )
    default = "minimal" if evaluation else "low"
    effort = str(os.getenv(env_name, default)).strip().lower() or default
    return {"reasoning": {"effort": effort}}


def response_diagnostic(response: Any) -> str:
    """Describe an empty/incomplete response without exposing prompt contents."""

    status = str(getattr(response, "status", None) or "unknown")
    details = getattr(response, "incomplete_details", None)
    reason = (
        details.get("reason")
        if isinstance(details, Mapping)
        else getattr(details, "reason", None)
    )
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
    return (
        f"status={status}, reason={reason or 'unknown'}, "
        f"input_tokens={input_tokens}, output_tokens={output_tokens}, "
        f"total_tokens={total_tokens}"
    )


def create_text_response(
    *,
    client: Any,
    request: Mapping[str, Any],
    label: str,
    token_budgets: Sequence[int],
    evaluation: bool = False,
) -> tuple[str, list[Any]]:
    """Call Responses API and retry empty output with a larger token budget."""

    budgets = [int(value) for value in token_budgets if int(value) > 0]
    if not budgets:
        raise ValueError("token_budgets must contain a positive value")

    responses: list[Any] = []
    last_diagnostic = "no response"
    for budget in budgets:
        kwargs = dict(request)
        model = str(kwargs.get("model") or "")
        kwargs.update(reasoning_options(model, evaluation=evaluation))
        kwargs["max_output_tokens"] = budget
        try:
            response = client.responses.create(**kwargs)
        except Exception as exc:
            raise LLMError(f"{label} request failed: {exc}") from exc
        responses.append(response)
        output_text = str(getattr(response, "output_text", None) or "").strip()
        if output_text:
            return output_text, responses
        last_diagnostic = response_diagnostic(response)

    raise LLMError(
        f"{label} returned no output after {len(responses)} attempt(s) "
        f"({last_diagnostic})"
    )


def summed_usage(responses: Sequence[Any]) -> dict[str, int]:
    """Sum token usage across retries so evaluation cost remains observable."""

    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for response in responses:
        usage = getattr(response, "usage", None)
        for name in totals:
            totals[name] += int(getattr(usage, name, 0) or 0)
    return totals
