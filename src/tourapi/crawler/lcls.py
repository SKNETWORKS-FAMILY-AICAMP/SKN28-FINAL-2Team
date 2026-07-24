from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .openapi_client import (
    DEFAULT_OPENAPI_CALL_BUDGET,
    DEFAULT_OPENAPI_MOBILE_APP,
    DEFAULT_OPENAPI_MOBILE_OS,
    DEFAULT_OPENAPI_PAGE_SIZE,
    DEFAULT_OPENAPI_RETRIES,
    DEFAULT_OPENAPI_TIMEOUT,
    OpenApiError,
    request_openapi_json,
    resolve_service_key,
)
from .openapi_response import as_int, response_body, response_items, validate_positive


@dataclass(frozen=True)
class LclsCodeResult:
    records: list[dict[str, Any]]
    calls_used: int
    max_depth: int


def fetch_lcls_code_tree(
    *,
    service_key: str | None = None,
    mobile_os: str = DEFAULT_OPENAPI_MOBILE_OS,
    mobile_app: str = DEFAULT_OPENAPI_MOBILE_APP,
    page_size: int = DEFAULT_OPENAPI_PAGE_SIZE,
    max_depth: int = 3,
    call_budget: int = DEFAULT_OPENAPI_CALL_BUDGET,
    timeout: float = DEFAULT_OPENAPI_TIMEOUT,
    retries: int = DEFAULT_OPENAPI_RETRIES,
) -> LclsCodeResult:
    validate_positive("page_size", page_size)
    validate_positive("call_budget", call_budget)
    validate_positive("retries", retries)
    if max_depth not in {1, 2, 3}:
        raise ValueError("max_depth must be 1, 2, or 3.")

    resolved_service_key = resolve_service_key(service_key)
    queue: list[tuple[int, dict[str, str]]] = [(1, {})]
    queued: set[tuple[tuple[str, str], ...]] = {tuple()}
    all_records: list[dict[str, Any]] = []
    calls_used = 0

    while queue:
        depth, query_params = queue.pop(0)
        if calls_used >= call_budget:
            raise OpenApiError(f"lcls code lookup would exceed call budget {call_budget}.")

        records, query_calls = fetch_lcls_code_records(
            resolved_service_key,
            mobile_os=mobile_os,
            mobile_app=mobile_app,
            page_size=page_size,
            query_params=query_params,
            timeout=timeout,
            retries=retries,
        )
        calls_used += query_calls
        if calls_used > call_budget:
            raise OpenApiError(
                f"lcls code lookup used {calls_used} calls, over budget {call_budget}."
            )

        all_records.extend(
            {
                "_query_depth": depth,
                "_query_lclsSystm1": query_params.get("lclsSystm1", ""),
                "_query_lclsSystm2": query_params.get("lclsSystm2", ""),
                **record,
            }
            for record in records
        )

        if depth >= max_depth:
            continue

        for record in records:
            child_query = _next_lcls_query(depth, query_params, record)
            if not child_query:
                continue
            child_key = tuple(sorted(child_query.items()))
            if child_key in queued:
                continue
            queued.add(child_key)
            queue.append((depth + 1, child_query))

    return LclsCodeResult(
        records=all_records,
        calls_used=calls_used,
        max_depth=max_depth,
    )


def fetch_lcls_code_records(
    service_key: str,
    *,
    mobile_os: str,
    mobile_app: str,
    page_size: int,
    query_params: dict[str, str] | None = None,
    timeout: float,
    retries: int,
) -> tuple[list[dict[str, Any]], int]:
    params = query_params or {}
    request_params: dict[str, str | int] = {
        "MobileOS": mobile_os,
        "MobileApp": mobile_app,
        "_type": "json",
        "numOfRows": page_size,
        "pageNo": 1,
        **params,
    }
    first_payload = request_openapi_json(
        "lclsSystmCode2",
        service_key,
        params=request_params,
        timeout=timeout,
        retries=retries,
    )
    calls_used = 1
    first_body = response_body(first_payload)
    records = response_items(first_body)

    total_count = as_int(first_body.get("totalCount")) or 0
    page_count = math.ceil(total_count / page_size) if total_count else 1
    for page_no in range(2, page_count + 1):
        request_params["pageNo"] = page_no
        payload = request_openapi_json(
            "lclsSystmCode2",
            service_key,
            params=request_params,
            timeout=timeout,
            retries=retries,
        )
        calls_used += 1
        records.extend(response_items(response_body(payload)))

    return records, calls_used


def _next_lcls_query(
    depth: int,
    query_params: dict[str, str],
    record: dict[str, Any],
) -> dict[str, str] | None:
    if depth == 1:
        lcls_systm1 = _extract_lcls_code(record, 1)
        return {"lclsSystm1": lcls_systm1} if lcls_systm1 else None

    if depth == 2:
        lcls_systm1 = query_params.get("lclsSystm1") or _extract_lcls_code(record, 1)
        lcls_systm2 = _extract_lcls_code(record, 2)
        if lcls_systm1 and lcls_systm2:
            return {"lclsSystm1": lcls_systm1, "lclsSystm2": lcls_systm2}

    return None


def _extract_lcls_code(record: dict[str, Any], level: int) -> str:
    candidate_keys = (
        f"lclsSystm{level}",
        f"lclsSystm{level}Cd",
        f"lclsSystm{level}Code",
        f"lclsSystm{level}code",
        f"lclsSystm{level}cd",
        "code",
        "cd",
    )
    for key in candidate_keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""
