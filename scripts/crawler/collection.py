from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..preprocessing.cleaner import first_value
from ..preprocessing.models import PlaceRules
from ..preprocessing.preprocessing import classify_place_record
from .openapi_client import OpenApiError


ALL_DATASETS = ("tourism", "lodging", "food", "leisure", "shopping")
REMOTE_DATASETS = ALL_DATASETS[1:]
COMPLETED_STATUSES = frozenset({"success", "no_data", "skipped_policy"})
IDENTITY_FIELDS = frozenset({"contentid", "contenttypeid", "contentId", "contentTypeId"})
DATASET_PRIORITY = {name: index for index, name in enumerate(ALL_DATASETS)}


@dataclass(frozen=True)
class CollectionStatus:
    row_count: int
    dataset_counts: dict[str, int]
    missing_datasets: tuple[str, ...]
    common_pending: int
    intro_pending: int


def read_place_csv(path: str | Path) -> list[dict[str, Any]]:
    csv_path = Path(path)
    if not csv_path.exists():
        return []
    with csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))
    normalize_place_field_names(rows)
    return rows


def normalize_place_field_names(rows: Sequence[dict[str, Any]]) -> None:
    variants_by_lower_name: dict[str, list[str]] = {}
    for row in rows:
        for field in row:
            variants = variants_by_lower_name.setdefault(field.lower(), [])
            if field not in variants:
                variants.append(field)

    for variants in variants_by_lower_name.values():
        if len(variants) < 2:
            continue
        canonical = max(variants, key=lambda field: sum(char.isupper() for char in field))
        for row in rows:
            for alternate in variants:
                if alternate == canonical:
                    continue
                alternate_value = row.pop(alternate, None)
                if row.get(canonical) in (None, "") and alternate_value not in (None, ""):
                    row[canonical] = alternate_value


def initialize_place_rows(
    unified_path: str | Path,
    tourism_source_path: str | Path,
    rules: PlaceRules,
) -> list[dict[str, Any]]:
    rows = read_place_csv(unified_path)
    if not rows:
        rows = read_place_csv(tourism_source_path)
        if not rows:
            raise ValueError(f"tourism seed CSV has no records: {tourism_source_path}")
        for row in rows:
            row["dataset"] = "tourism"

    _validate_unique_content_ids(rows)
    _mark_existing_details(rows)
    apply_tourism_intro_skips(rows, rules)
    return rows


def merge_list_records(
    rows: list[dict[str, Any]],
    *,
    dataset: str,
    records: Sequence[Mapping[str, Any]],
) -> int:
    if dataset not in ALL_DATASETS:
        raise ValueError(f"unsupported dataset: {dataset}")

    by_content_id = {first_value(row, "contentid", "contentId"): row for row in rows}
    added = 0
    for record in records:
        content_id = first_value(record, "contentid", "contentId")
        if not content_id:
            raise ValueError(f"{dataset} list record is missing contentid")
        existing = by_content_id.get(content_id)
        if existing is None:
            row = {"dataset": dataset, **dict(record)}
            rows.append(row)
            by_content_id[content_id] = row
            added += 1
            continue

        existing_dataset = first_value(existing, "dataset") or "tourism"
        for field, value in record.items():
            if value not in (None, "") and existing.get(field) in (None, ""):
                existing[str(field)] = value
        if DATASET_PRIORITY[dataset] > DATASET_PRIORITY.get(existing_dataset, -1):
            existing["dataset"] = dataset

    _validate_unique_content_ids(rows)
    return added


def apply_tourism_intro_skips(rows: Sequence[dict[str, Any]], rules: PlaceRules) -> int:
    skipped = 0
    for row in rows:
        if first_value(row, "dataset") != "tourism":
            continue
        classification = classify_place_record(row, rules)
        if classification.is_indexable and classification.target_collection != "regions":
            continue
        if first_value(row, "intro_fetch_status") in COMPLETED_STATUSES:
            continue
        row["intro_fetch_status"] = "skipped_policy"
        row["intro_fetch_error"] = ""
        skipped += 1
    return skipped


def collection_status(rows: Sequence[Mapping[str, Any]]) -> CollectionStatus:
    dataset_counts = {dataset: 0 for dataset in ALL_DATASETS}
    for row in rows:
        dataset = first_value(row, "dataset") or "tourism"
        if dataset in dataset_counts:
            dataset_counts[dataset] += 1
    return CollectionStatus(
        row_count=len(rows),
        dataset_counts=dataset_counts,
        missing_datasets=tuple(
            dataset for dataset in REMOTE_DATASETS if dataset_counts[dataset] == 0
        ),
        common_pending=len(pending_detail_indices(rows, "common")),
        intro_pending=len(pending_detail_indices(rows, "intro")),
    )


def pending_detail_indices(
    rows: Sequence[Mapping[str, Any]],
    detail_kind: str,
) -> list[int]:
    if detail_kind not in {"common", "intro"}:
        raise ValueError("detail_kind must be 'common' or 'intro'")
    status_field = f"{detail_kind}_fetch_status"
    return [
        index
        for index, row in enumerate(rows)
        if first_value(row, status_field) not in COMPLETED_STATUSES
    ]


def enrich_place_details(
    rows: list[dict[str, Any]],
    *,
    detail_kind: str,
    output_path: str | Path,
    service_key: str,
    mobile_os: str,
    mobile_app: str,
    call_budget: int,
    checkpoint_every: int,
    timeout: float,
    retries: int,
    fetcher: Callable[..., Mapping[str, Any]],
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> int:
    if call_budget < 0:
        raise ValueError("call_budget cannot be negative")
    if checkpoint_every < 1:
        raise ValueError("checkpoint_every must be at least 1")

    pending = pending_detail_indices(rows, detail_kind)
    targets = pending[:call_budget]
    calls_used = 0
    for row_index in targets:
        row = rows[row_index]
        content_id = first_value(row, "contentid", "contentId")
        content_type_id = first_value(row, "contenttypeid", "contentTypeId")
        if not content_id or not content_type_id:
            raise ValueError(f"row {row_index + 2} is missing contentid or contenttypeid")

        try:
            record = fetcher(
                service_key,
                content_id=content_id,
                content_type_id=content_type_id,
                mobile_os=mobile_os,
                mobile_app=mobile_app,
                timeout=timeout,
                retries=retries,
            )
            calls_used += 1
            apply_detail_record(row, detail_kind=detail_kind, record=record)
        except (OpenApiError, KeyboardInterrupt) as exc:
            row[f"{detail_kind}_fetch_status"] = "error"
            row[f"{detail_kind}_fetch_error"] = str(exc)
            row[f"{detail_kind}_fetched_at"] = datetime.now(UTC).isoformat()
            write_place_csv(rows, output_path)
            raise

        if calls_used % checkpoint_every == 0:
            write_place_csv(rows, output_path)
            if progress_callback:
                progress_callback(detail_kind, calls_used, len(targets))

    if targets:
        write_place_csv(rows, output_path)
    if progress_callback and calls_used % checkpoint_every:
        progress_callback(detail_kind, calls_used, len(targets))
    return calls_used


def apply_detail_record(
    row: dict[str, Any],
    *,
    detail_kind: str,
    record: Mapping[str, Any],
) -> None:
    if detail_kind not in {"common", "intro"}:
        raise ValueError("detail_kind must be 'common' or 'intro'")

    prefix = f"{detail_kind}_"
    audit_fields = {
        f"{detail_kind}_fetch_status",
        f"{detail_kind}_fetch_error",
        f"{detail_kind}_fetched_at",
    }
    for field in list(row):
        if field.startswith(prefix) and field not in audit_fields:
            row.pop(field)

    payload_fields = 0
    for field, value in record.items():
        if field in IDENTITY_FIELDS or field == "_detail_missing":
            continue
        row[f"{prefix}{field}"] = value
        if value not in (None, ""):
            payload_fields += 1

    row[f"{detail_kind}_fetch_status"] = "success" if payload_fields else "no_data"
    row[f"{detail_kind}_fetch_error"] = ""
    row[f"{detail_kind}_fetched_at"] = datetime.now(UTC).isoformat()


def write_place_csv(rows: Sequence[Mapping[str, Any]], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    preferred = ["dataset", "contentid", "contenttypeid", "title"]
    discovered = {str(field) for row in rows for field in row}
    fieldnames = [field for field in preferred if field in discovered]
    fieldnames.extend(sorted(discovered.difference(fieldnames)))
    temp_path = path.with_suffix(path.suffix + ".tmp")

    with temp_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})
    temp_path.replace(path)


def _mark_existing_details(rows: Sequence[dict[str, Any]]) -> None:
    for row in rows:
        if first_value(row, "common_overview") and not first_value(row, "common_fetch_status"):
            row["common_fetch_status"] = "success"
        intro_status = first_value(row, "intro_fetch_status")
        if intro_status in {"success", "no_data"}:
            row.setdefault("intro_fetch_error", "")


def _validate_unique_content_ids(rows: Sequence[Mapping[str, Any]]) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for row in rows:
        content_id = first_value(row, "contentid", "contentId")
        if not content_id:
            raise ValueError("place CSV contains a blank contentid")
        if content_id in seen:
            duplicates.append(content_id)
        seen.add(content_id)
    if duplicates:
        raise ValueError(f"place CSV contains duplicate contentids: {sorted(set(duplicates))[:10]}")


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else value
