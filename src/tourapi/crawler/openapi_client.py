from __future__ import annotations

from dataclasses import dataclass
from http.client import RemoteDisconnected
import json
import math
import os
import time
from typing import Any, Iterable, Literal, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .openapi_response import (
    as_int as _as_int,
    response_body as _response_body,
    response_items as _response_items,
    validate_positive as _validate_positive,
)


OPENAPI_BASE_URL = "https://apis.data.go.kr/B551011/KorService2"
DEFAULT_OPENAPI_AREA_CODE = "39"
DEFAULT_OPENAPI_LANG = "KOR"
DEFAULT_OPENAPI_MOBILE_OS = "ETC"
DEFAULT_OPENAPI_MOBILE_APP = "SKN28Final"
DEFAULT_OPENAPI_PAGE_SIZE = 100
DEFAULT_OPENAPI_CALL_BUDGET = 1000
DEFAULT_OPENAPI_RETRIES = 3
DEFAULT_OPENAPI_TIMEOUT = 20.0
SUCCESS_RESULT_CODE = "0000"
SERVICE_KEY_ENV_NAMES = (
    "KOREA_TOUR_API_KEY",
    "TOUR_API_KEY",
    "KTO_API_KEY",
    "DATA_GO_KR_SERVICE_KEY",
    "PUBLIC_DATA_SERVICE_KEY",
)
DetailMode = Literal["list", "common", "common-intro", "full"]
RegionMode = Literal["area-code", "address"]


@dataclass(frozen=True)
class OpenApiListFilter:
    label: str
    params: tuple[tuple[str, str], ...]

    def as_params(self) -> dict[str, str]:
        return dict(self.params)


@dataclass(frozen=True)
class OpenApiPreset:
    name: str
    label: str
    list_filters: tuple[OpenApiListFilter, ...]

    @property
    def content_type_ids(self) -> tuple[str, ...]:
        values: list[str] = []
        for list_filter in self.list_filters:
            content_type_id = list_filter.as_params().get("contentTypeId")
            if content_type_id:
                values.append(content_type_id)
        return tuple(values)


@dataclass(frozen=True)
class OpenApiFilterCount:
    list_filter: OpenApiListFilter
    total_count: int


@dataclass(frozen=True)
class OpenApiDatasetPlan:
    preset: OpenApiPreset
    detail_mode: DetailMode
    region_mode: RegionMode
    page_size: int
    filter_counts: tuple[OpenApiFilterCount, ...]
    planned_calls: int

    @property
    def total_count(self) -> int:
        return sum(filter_count.total_count for filter_count in self.filter_counts)


@dataclass(frozen=True)
class OpenApiDatasetResult:
    preset: OpenApiPreset
    filter_counts: tuple[OpenApiFilterCount, ...]
    total_count: int
    base_records: list[dict[str, Any]]
    common_records: list[dict[str, Any]]
    intro_records: list[dict[str, Any]]
    info_records: list[dict[str, Any]]
    calls_used: int
    detail_mode: DetailMode
    region_mode: RegionMode
    source_total_count: int


class OpenApiError(RuntimeError):
    """Raised when the official Korea Tour OpenAPI cannot return usable data."""


def _content_type_filter(content_type_id: str, label: str | None = None) -> OpenApiListFilter:
    return OpenApiListFilter(
        label or f"contentTypeId={content_type_id}",
        (("contentTypeId", content_type_id),),
    )


def _lcls_filter(code: str, label: str | None = None) -> OpenApiListFilter:
    return OpenApiListFilter(
        label or f"lclsSystm1={code}",
        (("lclsSystm1", code),),
    )


OPENAPI_CONTENT_TYPE_PRESETS: dict[str, OpenApiPreset] = {
    "tourism": OpenApiPreset(
        "tourism",
        "tourism attractions",
        (_content_type_filter("12", "contentTypeId=12 tourism attractions"),),
    ),
    "lodging": OpenApiPreset(
        "lodging",
        "lodging",
        (_content_type_filter("32", "contentTypeId=32 lodging"),),
    ),
    "food": OpenApiPreset(
        "food",
        "food",
        (_content_type_filter("39", "contentTypeId=39 food"),),
    ),
    "leisure": OpenApiPreset(
        "leisure",
        "leisure sports",
        (_content_type_filter("28", "contentTypeId=28 leisure sports"),),
    ),
    "shopping": OpenApiPreset(
        "shopping",
        "shopping",
        (_content_type_filter("38", "contentTypeId=38 shopping"),),
    ),
}
OPENAPI_LCLS_PRESETS: dict[str, OpenApiPreset] = {
    "tourism": OpenApiPreset(
        "tourism",
        "tourism attractions by new classification",
        (
            _lcls_filter("NA", "lclsSystm1=NA nature tourism"),
            _lcls_filter("HS", "lclsSystm1=HS history tourism"),
            _lcls_filter("EX", "lclsSystm1=EX experience tourism"),
            _lcls_filter("VE", "lclsSystm1=VE culture tourism"),
        ),
    ),
    "lodging": OpenApiPreset(
        "lodging",
        "lodging by new classification",
        (_lcls_filter("AC", "lclsSystm1=AC lodging"),),
    ),
    "food": OpenApiPreset(
        "food",
        "food by new classification",
        (_lcls_filter("FD", "lclsSystm1=FD food"),),
    ),
    "leisure": OpenApiPreset(
        "leisure",
        "leisure sports by new classification",
        (_lcls_filter("LS", "lclsSystm1=LS leisure sports"),),
    ),
    "shopping": OpenApiPreset(
        "shopping",
        "shopping by new classification",
        (_lcls_filter("SH", "lclsSystm1=SH shopping"),),
    ),
}
OPENAPI_PRESET_GROUPS: dict[str, dict[str, OpenApiPreset]] = {
    "content-type": OPENAPI_CONTENT_TYPE_PRESETS,
    "lcls": OPENAPI_LCLS_PRESETS,
}
OPENAPI_PRESETS = OPENAPI_CONTENT_TYPE_PRESETS


def fetch_openapi_dataset(
    preset: OpenApiPreset,
    *,
    service_key: str | None = None,
    area_code: str = DEFAULT_OPENAPI_AREA_CODE,
    region_mode: RegionMode = "area-code",
    address_keywords: Sequence[str] = ("제주특별자치", "제주시", "서귀포시"),
    mobile_os: str = DEFAULT_OPENAPI_MOBILE_OS,
    mobile_app: str = DEFAULT_OPENAPI_MOBILE_APP,
    page_size: int = DEFAULT_OPENAPI_PAGE_SIZE,
    detail_mode: DetailMode = "common",
    call_budget: int = DEFAULT_OPENAPI_CALL_BUDGET,
    timeout: float = DEFAULT_OPENAPI_TIMEOUT,
    retries: int = DEFAULT_OPENAPI_RETRIES,
    plan: OpenApiDatasetPlan | None = None,
) -> OpenApiDatasetResult:
    _validate_positive("page_size", page_size)
    _validate_positive("call_budget", call_budget)
    _validate_positive("retries", retries)

    resolved_service_key = resolve_service_key(service_key)
    if plan is None:
        plan = plan_openapi_dataset(
            preset,
            service_key=resolved_service_key,
            area_code=area_code,
            region_mode=region_mode,
            mobile_os=mobile_os,
            mobile_app=mobile_app,
            page_size=page_size,
            detail_mode=detail_mode,
            timeout=timeout,
            retries=retries,
        )
    elif (
        plan.preset != preset
        or plan.detail_mode != detail_mode
        or plan.page_size != page_size
        or plan.region_mode != region_mode
    ):
        raise OpenApiError("The provided OpenAPI plan does not match the requested dataset.")

    if plan.planned_calls > call_budget:
        raise OpenApiError(
            f"{preset.name} would use about {plan.planned_calls} calls with detail_mode="
            f"{detail_mode!r}, over budget {call_budget}. Use a smaller detail mode "
            "or run one preset at a time."
        )

    base_records: list[dict[str, Any]] = []
    calls_used = len(plan.filter_counts)
    for filter_count in plan.filter_counts:
        records, list_calls = fetch_area_based_records(
            resolved_service_key,
            list_filter=filter_count.list_filter,
            area_code=area_code if region_mode == "area-code" else None,
            mobile_os=mobile_os,
            mobile_app=mobile_app,
            page_size=page_size,
            timeout=timeout,
            retries=retries,
        )
        calls_used += list_calls
        base_records.extend(records)

    if region_mode == "address":
        base_records = [
            record
            for record in base_records
            if _record_matches_region(record, area_code=area_code, address_keywords=address_keywords)
        ]

    base_records = _deduplicate_records(base_records)
    planned_detail_calls = _per_record_call_count(detail_mode) * len(base_records)
    if calls_used + planned_detail_calls > call_budget:
        raise OpenApiError(
            f"{preset.name} would use about {calls_used + planned_detail_calls} calls after "
            f"region filtering, over budget {call_budget}. Use a smaller detail mode "
            "or run one preset at a time."
        )
    common_records: list[dict[str, Any]] = []
    intro_records: list[dict[str, Any]] = []
    info_records: list[dict[str, Any]] = []

    if detail_mode in {"common", "common-intro", "full"}:
        for record in base_records:
            common_records.append(
                fetch_detail_common(
                    resolved_service_key,
                    content_id=_content_id(record),
                    content_type_id=_content_type_id(record),
                    mobile_os=mobile_os,
                    mobile_app=mobile_app,
                    timeout=timeout,
                    retries=retries,
                )
            )
            calls_used += 1

    if detail_mode in {"common-intro", "full"}:
        for record in base_records:
            intro_records.append(
                fetch_detail_intro(
                    resolved_service_key,
                    content_id=_content_id(record),
                    content_type_id=_content_type_id(record),
                    mobile_os=mobile_os,
                    mobile_app=mobile_app,
                    timeout=timeout,
                    retries=retries,
                )
            )
            calls_used += 1

    if detail_mode == "full":
        for record in base_records:
            info_records.extend(
                fetch_detail_info(
                    resolved_service_key,
                    content_id=_content_id(record),
                    content_type_id=_content_type_id(record),
                    mobile_os=mobile_os,
                    mobile_app=mobile_app,
                    timeout=timeout,
                    retries=retries,
                )
            )
            calls_used += 1

    return OpenApiDatasetResult(
        preset=preset,
        filter_counts=plan.filter_counts,
        total_count=len(base_records),
        base_records=base_records,
        common_records=common_records,
        intro_records=intro_records,
        info_records=info_records,
        calls_used=calls_used,
        detail_mode=detail_mode,
        region_mode=region_mode,
        source_total_count=plan.total_count,
    )


def plan_openapi_dataset(
    preset: OpenApiPreset,
    *,
    service_key: str | None = None,
    area_code: str = DEFAULT_OPENAPI_AREA_CODE,
    region_mode: RegionMode = "area-code",
    mobile_os: str = DEFAULT_OPENAPI_MOBILE_OS,
    mobile_app: str = DEFAULT_OPENAPI_MOBILE_APP,
    page_size: int = DEFAULT_OPENAPI_PAGE_SIZE,
    detail_mode: DetailMode = "common",
    timeout: float = DEFAULT_OPENAPI_TIMEOUT,
    retries: int = DEFAULT_OPENAPI_RETRIES,
) -> OpenApiDatasetPlan:
    _validate_positive("page_size", page_size)
    _validate_positive("retries", retries)

    resolved_service_key = resolve_service_key(service_key)
    filter_counts = fetch_total_counts(
        resolved_service_key,
        preset.list_filters,
        area_code=area_code if region_mode == "area-code" else None,
        mobile_os=mobile_os,
        mobile_app=mobile_app,
        timeout=timeout,
        retries=retries,
    )
    return OpenApiDatasetPlan(
        preset=preset,
        detail_mode=detail_mode,
        region_mode=region_mode,
        page_size=page_size,
        filter_counts=filter_counts,
        planned_calls=estimate_openapi_call_count(
            filter_counts=filter_counts,
            page_size=page_size,
            detail_mode=detail_mode if region_mode == "area-code" else "list",
        ),
    )


def resolve_service_key(explicit_service_key: str | None = None) -> str:
    if explicit_service_key:
        return explicit_service_key

    for env_name in SERVICE_KEY_ENV_NAMES:
        value = os.getenv(env_name)
        if value:
            return value

    names = ", ".join(SERVICE_KEY_ENV_NAMES)
    raise OpenApiError(f"TourAPI service key is missing. Set one of: {names}")


def fetch_total_count(
    service_key: str,
    list_filters: Sequence[OpenApiListFilter | str],
    *,
    area_code: str | None,
    mobile_os: str,
    mobile_app: str,
    timeout: float,
    retries: int,
) -> int:
    return sum(
        filter_count.total_count
        for filter_count in fetch_total_counts(
            service_key,
            list_filters,
            area_code=area_code,
            mobile_os=mobile_os,
            mobile_app=mobile_app,
            timeout=timeout,
            retries=retries,
        )
    )


def fetch_total_counts(
    service_key: str,
    list_filters: Sequence[OpenApiListFilter | str],
    *,
    area_code: str | None,
    mobile_os: str,
    mobile_app: str,
    timeout: float,
    retries: int,
) -> tuple[OpenApiFilterCount, ...]:
    normalized_filters = _normalize_list_filters(list_filters)
    counts: list[OpenApiFilterCount] = []
    for list_filter in normalized_filters:
        payload = request_openapi_json(
            "areaBasedList2",
            service_key,
            params={
                **_base_list_params(mobile_os=mobile_os, mobile_app=mobile_app),
                "numOfRows": 1,
                "pageNo": 1,
                **_optional_area_param(area_code),
                **list_filter.as_params(),
            },
            timeout=timeout,
            retries=retries,
        )
        counts.append(
            OpenApiFilterCount(
                list_filter=list_filter,
                total_count=_as_int(_response_body(payload).get("totalCount")) or 0,
            )
        )
    return tuple(counts)


def fetch_area_based_records(
    service_key: str,
    *,
    list_filter: OpenApiListFilter | str | None = None,
    content_type_id: str | None = None,
    area_code: str | None,
    mobile_os: str,
    mobile_app: str,
    page_size: int,
    timeout: float,
    retries: int,
) -> tuple[list[dict[str, Any]], int]:
    if list_filter is None:
        if content_type_id is None:
            raise ValueError("Either list_filter or content_type_id is required.")
        list_filter = content_type_id

    normalized_filter = _normalize_list_filter(list_filter)
    records: list[dict[str, Any]] = []
    first_payload = request_openapi_json(
        "areaBasedList2",
        service_key,
        params={
            **_base_list_params(mobile_os=mobile_os, mobile_app=mobile_app),
            "numOfRows": page_size,
            "pageNo": 1,
            **_optional_area_param(area_code),
            **normalized_filter.as_params(),
        },
        timeout=timeout,
        retries=retries,
    )
    calls_used = 1
    first_body = _response_body(first_payload)
    records.extend(_response_items(first_body))

    total_count = _as_int(first_body.get("totalCount")) or 0
    page_count = math.ceil(total_count / page_size) if total_count else 1
    for page_no in range(2, page_count + 1):
        payload = request_openapi_json(
            "areaBasedList2",
            service_key,
            params={
                **_base_list_params(mobile_os=mobile_os, mobile_app=mobile_app),
                "numOfRows": page_size,
                "pageNo": page_no,
                **_optional_area_param(area_code),
                **normalized_filter.as_params(),
            },
            timeout=timeout,
            retries=retries,
        )
        calls_used += 1
        records.extend(_response_items(_response_body(payload)))

    return records, calls_used


def fetch_detail_common(
    service_key: str,
    *,
    content_id: str,
    content_type_id: str = "",
    mobile_os: str,
    mobile_app: str,
    timeout: float,
    retries: int,
) -> dict[str, Any]:
    payload = request_openapi_json(
        "detailCommon2",
        service_key,
        params={
            "MobileOS": mobile_os,
            "MobileApp": mobile_app,
            "_type": "json",
            "contentId": content_id,
        },
        timeout=timeout,
        retries=retries,
    )
    return _with_detail_identity(_first_response_item(_response_body(payload)), content_id, content_type_id)


def fetch_detail_intro(
    service_key: str,
    *,
    content_id: str,
    content_type_id: str,
    mobile_os: str,
    mobile_app: str,
    timeout: float,
    retries: int,
) -> dict[str, Any]:
    payload = request_openapi_json(
        "detailIntro2",
        service_key,
        params={
            "MobileOS": mobile_os,
            "MobileApp": mobile_app,
            "_type": "json",
            "contentId": content_id,
            "contentTypeId": content_type_id,
        },
        timeout=timeout,
        retries=retries,
    )
    return _with_detail_identity(_first_response_item(_response_body(payload)), content_id, content_type_id)


def fetch_detail_info(
    service_key: str,
    *,
    content_id: str,
    content_type_id: str,
    mobile_os: str,
    mobile_app: str,
    timeout: float,
    retries: int,
) -> list[dict[str, Any]]:
    payload = request_openapi_json(
        "detailInfo2",
        service_key,
        params={
            "MobileOS": mobile_os,
            "MobileApp": mobile_app,
            "_type": "json",
            "contentId": content_id,
            "contentTypeId": content_type_id,
        },
        timeout=timeout,
        retries=retries,
    )
    return [
        _with_detail_identity(item, content_id, content_type_id)
        for item in _response_items(_response_body(payload))
    ]


def request_openapi_json(
    operation: str,
    service_key: str,
    *,
    params: dict[str, str | int],
    timeout: float,
    retries: int,
) -> dict[str, Any]:
    query = _build_query(service_key, params)
    request = Request(
        f"{OPENAPI_BASE_URL}/{operation}?{query}",
        headers={
            "Accept": "application/json",
            "User-Agent": "skn28-korea-tour-openapi-fetcher/1.0",
        },
        method="GET",
    )
    raw_body = _open_with_retries(request, timeout=timeout, retries=retries)
    try:
        payload = json.loads(raw_body.decode("utf-8-sig"))
    except json.JSONDecodeError as exc:
        preview = raw_body[:300].decode("utf-8", errors="replace")
        raise OpenApiError(f"TourAPI returned invalid JSON: {preview}") from exc

    if not isinstance(payload, dict):
        raise OpenApiError("TourAPI returned a non-object JSON response.")
    _raise_for_api_error(payload)
    return payload


def estimate_openapi_call_count(
    *,
    page_size: int,
    detail_mode: DetailMode,
    filter_counts: Sequence[OpenApiFilterCount] | None = None,
    total_count: int | None = None,
    content_type_count: int | None = None,
) -> int:
    if filter_counts is None:
        if total_count is None or content_type_count is None:
            raise ValueError("filter_counts or total_count/content_type_count is required.")
        filter_counts = (
            OpenApiFilterCount(
                list_filter=_content_type_filter(""),
                total_count=total_count,
            ),
        )
        count_calls = content_type_count
        list_calls = math.ceil(total_count / page_size) if total_count else content_type_count
    else:
        total_count = sum(filter_count.total_count for filter_count in filter_counts)
        count_calls = len(filter_counts)
        list_calls = sum(
            math.ceil(filter_count.total_count / page_size) if filter_count.total_count else 1
            for filter_count in filter_counts
        )

    per_record_calls = _per_record_call_count(detail_mode)
    return count_calls + list_calls + (total_count * per_record_calls)


def _build_query(service_key: str, params: dict[str, str | int]) -> str:
    encoded_params = urlencode(params)
    encoded_service_key = service_key if "%" in service_key else quote(service_key, safe="")
    return f"serviceKey={encoded_service_key}&{encoded_params}"


def _open_with_retries(request: Request, *, timeout: float, retries: int) -> bytes:
    last_error: BaseException | None = None
    for attempt in range(1, retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:300]
            raise OpenApiError(f"TourAPI HTTP error: {exc.code} {exc.reason}. {body}") from exc
        except (
            ConnectionResetError,
            RemoteDisconnected,
            TimeoutError,
            URLError,
        ) as exc:
            last_error = exc

        if attempt < retries:
            time.sleep(min(2 ** (attempt - 1), 5))

    raise OpenApiError(f"TourAPI request failed after {retries} attempt(s): {last_error}") from last_error


def _raise_for_api_error(payload: dict[str, Any]) -> None:
    direct_result_code = payload.get("resultCode")
    direct_result_message = payload.get("resultMsg")
    if direct_result_code is not None or direct_result_message is not None:
        if str(direct_result_code or "") != SUCCESS_RESULT_CODE:
            raise OpenApiError(
                f"TourAPI error {direct_result_code or 'unknown'}: "
                f"{direct_result_message or 'unknown error'}"
            )

    response = payload.get("response")
    if not isinstance(response, dict):
        raise OpenApiError(f"TourAPI response is missing 'response': {payload!r}")

    header = response.get("header")
    if not isinstance(header, dict):
        raise OpenApiError("TourAPI response is missing 'header'.")

    result_code = str(header.get("resultCode") or "")
    if result_code != SUCCESS_RESULT_CODE:
        result_message = header.get("resultMsg", "unknown error")
        raise OpenApiError(f"TourAPI error {result_code}: {result_message}")


def _first_response_item(body: dict[str, Any]) -> dict[str, Any]:
    items = _response_items(body)
    return items[0] if items else {}


def _base_list_params(*, mobile_os: str, mobile_app: str) -> dict[str, str]:
    return {
        "MobileOS": mobile_os,
        "MobileApp": mobile_app,
        "_type": "json",
        "arrange": "A",
    }


def _optional_area_param(area_code: str | None) -> dict[str, str]:
    return {"areaCode": area_code} if area_code else {}


def _record_matches_region(
    record: dict[str, Any],
    *,
    area_code: str,
    address_keywords: Sequence[str],
) -> bool:
    record_area_code = str(record.get("areacode") or record.get("areaCode") or "").strip()
    if record_area_code == area_code:
        return True

    addr1 = str(record.get("addr1") or record.get("addr") or record.get("address") or "").strip()
    addr2 = str(record.get("addr2") or "").strip()
    address = f"{addr1} {addr2}".strip()
    return any(
        keyword and (addr1.startswith(keyword) or address.startswith(keyword))
        for keyword in address_keywords
    )


def _per_record_call_count(detail_mode: DetailMode) -> int:
    return {
        "list": 0,
        "common": 1,
        "common-intro": 2,
        "full": 3,
    }[detail_mode]


def _normalize_list_filters(
    list_filters: Sequence[OpenApiListFilter | str],
) -> tuple[OpenApiListFilter, ...]:
    return tuple(_normalize_list_filter(value) for value in list_filters)


def _normalize_list_filter(value: OpenApiListFilter | str) -> OpenApiListFilter:
    if isinstance(value, OpenApiListFilter):
        return value
    return _content_type_filter(str(value))


def _with_detail_identity(
    item: dict[str, Any],
    content_id: str,
    content_type_id: str = "",
) -> dict[str, Any]:
    if item:
        item.setdefault("contentid", content_id)
        if content_type_id:
            item.setdefault("contenttypeid", content_type_id)
        return item

    fallback: dict[str, Any] = {"contentid": content_id, "_detail_missing": True}
    if content_type_id:
        fallback["contenttypeid"] = content_type_id
    return fallback


def _deduplicate_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_content_ids: set[str] = set()
    for record in records:
        content_id = _content_id(record)
        if not content_id or content_id in seen_content_ids:
            continue
        seen_content_ids.add(content_id)
        deduped.append(record)
    return deduped


def _content_id(record: dict[str, Any]) -> str:
    value = record.get("contentid") or record.get("contentId")
    return "" if value is None else str(value).strip()


def _content_type_id(record: dict[str, Any]) -> str:
    value = record.get("contenttypeid") or record.get("contentTypeId")
    return "" if value is None else str(value).strip()


