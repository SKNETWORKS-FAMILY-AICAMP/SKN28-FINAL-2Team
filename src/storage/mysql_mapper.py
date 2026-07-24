from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


CONTENT_TYPE_NAMES = {
    12: "tourist_attraction",
    14: "cultural_facility",
    28: "leisure_sports",
    32: "lodging",
    38: "shopping",
    39: "food",
}

INTRO_CONTROL_FIELDS = {
    "intro_fetch_error",
    "intro_fetch_status",
    "intro_fetched_at",
}
COMMON_CONTROL_FIELDS = {
    "common_fetch_error",
    "common_fetch_status",
    "common_fetched_at",
}


@dataclass(frozen=True)
class MySQLImportData:
    content_types: list[tuple[Any, ...]]
    lcls_categories: list[tuple[Any, ...]]
    places: list[tuple[Any, ...]]
    common_details: list[tuple[Any, ...]]
    intro_details: list[tuple[Any, ...]]
    images: list[tuple[Any, ...]]
    search_documents: list[tuple[Any, ...]]
    search_chunks: list[tuple[Any, ...]]
    fetch_records: list[tuple[Any, ...]]


def build_mysql_import_data(
    raw_csv_path: str | Path,
    rag_json_path: str | Path,
    *,
    lcls_csv_path: str | Path | None = None,
    rules_path: str | Path | None = None,
) -> MySQLImportData:
    raw_rows = _read_csv(raw_csv_path)
    if not raw_rows:
        raise ValueError("raw TourAPI CSV contains no rows")
    payload = json.loads(Path(rag_json_path).read_text(encoding="utf-8"))
    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("RAG JSON must contain a non-empty documents list")

    document_by_content_id = _document_index(documents)
    exclusion_reasons = _exclusion_reasons(payload, rules_path)
    lcls_names = _lcls_name_index(lcls_csv_path)
    generated_at = parse_datetime(payload.get("generated_at"))
    preprocessing_version = _optional_text(payload.get("preprocessing_version"))

    content_type_ids = {_required_int(row, "contenttypeid") for row in raw_rows}
    content_types = [
        (content_type_id, CONTENT_TYPE_NAMES.get(content_type_id, "unknown"))
        for content_type_id in sorted(content_type_ids)
    ]
    lcls_categories = _lcls_categories(raw_rows, lcls_names)

    places: list[tuple[Any, ...]] = []
    common_details: list[tuple[Any, ...]] = []
    intro_details: list[tuple[Any, ...]] = []
    images: list[tuple[Any, ...]] = []
    search_documents: list[tuple[Any, ...]] = []
    search_chunks: list[tuple[Any, ...]] = []
    fetch_records: list[tuple[Any, ...]] = []

    seen_content_ids: set[int] = set()
    for row in raw_rows:
        content_id = _required_int(row, "contentid")
        if content_id in seen_content_ids:
            raise ValueError(f"duplicate contentid in raw CSV: {content_id}")
        seen_content_ids.add(content_id)

        places.append(_place_row(row, content_id))
        common_details.append(_common_detail_row(row, content_id))
        intro_details.append(_intro_detail_row(row, content_id))
        image = _image_row(row, content_id)
        if image is not None:
            images.append(image)

        document = document_by_content_id.get(str(content_id))
        search_document, chunk = _search_rows(
            row,
            content_id,
            document,
            exclusion_reasons.get(str(content_id)),
            preprocessing_version,
            generated_at,
        )
        search_documents.append(search_document)
        if chunk is not None:
            search_chunks.append(chunk)

        fetch_records.extend(_fetch_rows(row, content_id))

    unknown_documents = set(document_by_content_id).difference(
        str(content_id) for content_id in seen_content_ids
    )
    if unknown_documents:
        sample = ", ".join(sorted(unknown_documents)[:5])
        raise ValueError(f"RAG JSON contains content IDs missing from raw CSV: {sample}")

    return MySQLImportData(
        content_types=content_types,
        lcls_categories=lcls_categories,
        places=places,
        common_details=common_details,
        intro_details=intro_details,
        images=images,
        search_documents=search_documents,
        search_chunks=search_chunks,
        fetch_records=fetch_records,
    )


def parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if len(text) == 14 and text.isdigit():
            return datetime.strptime(text, "%Y%m%d%H%M%S")
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(UTC).replace(tzinfo=None)
        return parsed
    except ValueError as exc:
        raise ValueError(f"invalid datetime value: {text}") from exc


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _document_index(documents: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for document in documents:
        metadata = document.get("metadata")
        if not isinstance(metadata, Mapping):
            raise ValueError("each RAG document requires metadata")
        content_id = str(metadata.get("contentid") or "").strip()
        text = str(document.get("embedding_text") or "").strip()
        if not content_id or not text:
            raise ValueError("each RAG document requires contentid and embedding_text")
        if content_id in indexed:
            raise ValueError(f"duplicate contentid in RAG JSON: {content_id}")
        indexed[content_id] = document
    return indexed


def _exclusion_reasons(
    payload: Mapping[str, Any], rules_path: str | Path | None
) -> dict[str, str]:
    reasons: dict[str, str] = {}
    if rules_path is not None and Path(rules_path).exists():
        rules = json.loads(Path(rules_path).read_text(encoding="utf-8"))
        configured = rules.get("excluded_content_ids", {})
        if isinstance(configured, Mapping):
            reasons.update(
                (str(content_id), str(reason))
                for content_id, reason in configured.items()
            )
    groups = payload.get("place_groups", [])
    if isinstance(groups, list):
        for group in groups:
            if not isinstance(group, Mapping):
                continue
            for member in group.get("members", []):
                if (
                    isinstance(member, Mapping)
                    and member.get("relationship_type") == "exact_duplicate"
                ):
                    reasons[str(member.get("contentid"))] = "exact duplicate place"
    return reasons


def _lcls_name_index(path: str | Path | None) -> dict[str, str]:
    if path is None or not Path(path).exists():
        return {}
    names: dict[str, str] = {}
    for row in _read_csv(path):
        code = str(row.get("code") or "").strip()
        name = str(row.get("name") or "").strip()
        if code and name:
            names[code] = name
    return names


def _lcls_categories(
    raw_rows: Sequence[Mapping[str, str]], names: Mapping[str, str]
) -> list[tuple[Any, ...]]:
    categories: dict[str, tuple[Any, ...]] = {}
    for row in raw_rows:
        lcls1 = _first(row, "common_lclsSystm1", "lclsSystm1")
        lcls2 = _first(row, "common_lclsSystm2", "lclsSystm2")
        lcls3 = _first(row, "common_lclsSystm3", "lclsSystm3")
        if not lcls1 or not lcls2 or not lcls3:
            raise ValueError(f"contentid={row.get('contentid')} is missing lcls codes")
        categories[lcls3] = (
            lcls3,
            lcls1,
            names.get(lcls1),
            lcls2,
            names.get(lcls2),
            names.get(lcls3),
        )
    return [categories[code] for code in sorted(categories)]


def _place_row(row: Mapping[str, str], content_id: int) -> tuple[Any, ...]:
    longitude = _required_decimal(row, "common_mapx", "mapx")
    latitude = _required_decimal(row, "common_mapy", "mapy")
    lcls3 = _first(row, "common_lclsSystm3", "lclsSystm3")
    if not lcls3:
        raise ValueError(f"contentid={content_id} is missing lcls3")
    return (
        content_id,
        _required_int(row, "contenttypeid"),
        lcls3,
        _first(row, "common_title", "title") or str(content_id),
        _first(row, "common_addr1", "addr1"),
        _first(row, "common_addr2", "addr2"),
        _optional_int(_first(row, "common_areacode", "areacode")),
        _optional_int(_first(row, "common_sigungucode", "sigungucode")),
        _first(row, "common_zipcode", "zipcode"),
        longitude,
        latitude,
        longitude,
        latitude,
        _optional_int(_first(row, "common_mlevel", "mlevel")),
        parse_datetime(_first(row, "common_createdtime", "createdtime")),
        parse_datetime(_first(row, "common_modifiedtime", "modifiedtime")),
    )


def _common_detail_row(row: Mapping[str, str], content_id: int) -> tuple[Any, ...]:
    return (
        content_id,
        _first(row, "common_tel", "tel"),
        _first(row, "common_telname"),
        _first(row, "common_homepage"),
        _first(row, "common_overview"),
        _first(row, "common_cpyrhtDivCd", "cpyrhtDivCd"),
    )


def _intro_detail_row(row: Mapping[str, str], content_id: int) -> tuple[Any, ...]:
    payload = _prefixed_payload(row, "intro_", INTRO_CONTROL_FIELDS)
    return (
        content_id,
        _first(
            row,
            "intro_infocenter",
            "intro_infocenterculture",
            "intro_infocenterleports",
            "intro_infocenterlodging",
            "intro_infocentershopping",
            "intro_infocenterfood",
        ),
        _first(
            row,
            "intro_usetime",
            "intro_usetimeculture",
            "intro_usetimeleports",
            "intro_opentime",
            "intro_opentimefood",
        ),
        _first(
            row,
            "intro_restdate",
            "intro_restdateculture",
            "intro_restdateleports",
            "intro_restdateshopping",
            "intro_restdatefood",
        ),
        _first(
            row,
            "intro_parking",
            "intro_parkingculture",
            "intro_parkingleports",
            "intro_parkinglodging",
            "intro_parkingshopping",
            "intro_parkingfood",
        ),
        _first(
            row,
            "intro_reservation",
            "intro_reservationlodging",
            "intro_reservationfood",
        ),
        _first(row, "intro_usefee", "intro_usefeeleports"),
        _first(row, "intro_checkintime"),
        _first(row, "intro_checkouttime"),
        _json(payload),
    )


def _image_row(row: Mapping[str, str], content_id: int) -> tuple[Any, ...] | None:
    image_url = _first(row, "common_firstimage", "firstimage")
    if not image_url:
        return None
    return (
        content_id,
        image_url,
        _first(row, "common_firstimage2", "firstimage2"),
        "representative",
        0,
    )


def _search_rows(
    raw_row: Mapping[str, str],
    content_id: int,
    document: Mapping[str, Any] | None,
    exclusion_reason: str | None,
    preprocessing_version: str | None,
    generated_at: datetime | None,
) -> tuple[tuple[Any, ...], tuple[Any, ...] | None]:
    dataset = str(raw_row.get("dataset") or "unknown").strip()
    if document is None:
        reason = exclusion_reason or "excluded by preprocessing policy"
        tags = _machine_tags(dataset=dataset)
        return (
            content_id,
            content_id,
            dataset,
            False,
            False,
            False,
            True,
            reason,
            None,
            _json(tags),
            preprocessing_version,
            generated_at,
        ), None

    metadata = document["metadata"]
    search_text = str(document["embedding_text"]).strip()
    tags = _unique_strings(
        [
            *metadata.get("tags", []),
            *_machine_tags(
                dataset=str(metadata.get("dataset") or dataset),
                target_collection=metadata.get("target_collection"),
                place_subtype=metadata.get("place_subtype"),
                recommendation_scope=metadata.get("recommendation_scope"),
            ),
        ]
    )
    search_document = (
        content_id,
        content_id,
        str(metadata.get("dataset") or dataset),
        True,
        bool(metadata.get("route_eligible", False)),
        bool(metadata.get("schedule_eligible", False)),
        bool(metadata.get("requires_verification", False)),
        None,
        search_text,
        _json(tags),
        _optional_text(metadata.get("preprocessing_version")) or preprocessing_version,
        generated_at,
    )
    return search_document, (content_id, 0, search_text)


def _fetch_rows(row: Mapping[str, str], content_id: int) -> list[tuple[Any, ...]]:
    records: list[tuple[Any, ...]] = []
    for prefix, endpoint, controls in (
        ("common_", "detailCommon2", COMMON_CONTROL_FIELDS),
        ("intro_", "detailIntro2", INTRO_CONTROL_FIELDS),
    ):
        status = str(row.get(f"{prefix}fetch_status") or "not_fetched").strip()
        records.append(
            (
                content_id,
                endpoint,
                status,
                _optional_text(row.get(f"{prefix}fetch_error")),
                parse_datetime(row.get(f"{prefix}fetched_at")),
                _json(_prefixed_payload(row, prefix, controls)),
            )
        )
    return records


def _prefixed_payload(
    row: Mapping[str, str], prefix: str, excluded_fields: set[str]
) -> dict[str, str]:
    return {
        key.removeprefix(prefix): value.strip()
        for key, value in row.items()
        if key.startswith(prefix)
        and key not in excluded_fields
        and value is not None
        and value.strip()
    }


def _machine_tags(
    *,
    dataset: str,
    target_collection: Any = None,
    place_subtype: Any = None,
    recommendation_scope: Any = None,
) -> list[str]:
    values = {
        "dataset": dataset,
        "target_collection": target_collection,
        "place_subtype": place_subtype,
        "recommendation_scope": recommendation_scope,
    }
    return [f"{key}:{value}" for key, value in values.items() if value]


def _unique_strings(values: Sequence[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _first(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = _optional_text(row.get(key))
        if value is not None:
            return value
    return None


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _required_int(row: Mapping[str, Any], key: str) -> int:
    value = _optional_int(row.get(key))
    if value is None:
        raise ValueError(f"required integer field is missing: {key}")
    return value


def _optional_int(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"invalid integer value: {text}") from exc


def _required_decimal(row: Mapping[str, Any], *keys: str) -> Decimal:
    text = _first(row, *keys)
    if text is None:
        raise ValueError(f"required decimal field is missing: {keys[0]}")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"invalid decimal value: {text}") from exc


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
