from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .csv_values import csv_value


CONTENT_ID_FIELDS = ("contentid", "contentId")
CONTENT_TYPE_ID_FIELDS = ("contenttypeid", "contentTypeId")


def combine_dataset_records(
    *,
    dataset: str,
    base_records: Iterable[Mapping[str, Any]],
    common_records: Iterable[Mapping[str, Any]] = (),
    intro_records: Iterable[Mapping[str, Any]] = (),
    info_records: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Combine one dataset's API responses into one row per content ID."""
    rows: list[dict[str, Any]] = []
    rows_by_content_id: dict[str, dict[str, Any]] = {}

    for record in base_records:
        content_id = _required_content_id(record)
        if content_id in rows_by_content_id:
            raise ValueError(f"duplicate base content ID: {content_id}")
        row = {"dataset": dataset, **record}
        rows.append(row)
        rows_by_content_id[content_id] = row

    _merge_prefixed_records(
        rows,
        rows_by_content_id,
        dataset=dataset,
        records=common_records,
        prefix="common_",
    )
    _merge_prefixed_records(
        rows,
        rows_by_content_id,
        dataset=dataset,
        records=intro_records,
        prefix="intro_",
    )

    for record in info_records:
        content_id = _required_content_id(record)
        row = _get_or_create_row(rows, rows_by_content_id, dataset, record)
        row.setdefault("info_items", []).append(dict(record))

    return rows


def write_records_csv(
    records: Iterable[Mapping[str, Any]],
    output_path: str | Path,
    *,
    preferred_field_order: Sequence[str] = (),
) -> int:
    rows = list(records)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = _fieldnames(rows, preferred_field_order)
    with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field)) for field in fieldnames})

    return len(rows)


def write_json(payload: Mapping[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fieldnames(
    rows: Sequence[Mapping[str, Any]],
    preferred_field_order: Sequence[str],
) -> list[str]:
    discovered: set[str] = set()
    for row in rows:
        discovered.update(str(key) for key in row.keys())

    ordered = [field for field in preferred_field_order if field in discovered]
    ordered.extend(sorted(discovered.difference(ordered)))
    return ordered


def _merge_prefixed_records(
    rows: list[dict[str, Any]],
    rows_by_content_id: dict[str, dict[str, Any]],
    *,
    dataset: str,
    records: Iterable[Mapping[str, Any]],
    prefix: str,
) -> None:
    identifier_fields = {*CONTENT_ID_FIELDS, *CONTENT_TYPE_ID_FIELDS}
    for record in records:
        content_id = _required_content_id(record)
        row = _get_or_create_row(rows, rows_by_content_id, dataset, record)
        for field, value in record.items():
            if field not in identifier_fields:
                row[f"{prefix}{field}"] = value


def _get_or_create_row(
    rows: list[dict[str, Any]],
    rows_by_content_id: dict[str, dict[str, Any]],
    dataset: str,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    content_id = _required_content_id(record)
    existing = rows_by_content_id.get(content_id)
    if existing is not None:
        return existing

    row: dict[str, Any] = {"dataset": dataset}
    for field in (*CONTENT_ID_FIELDS, *CONTENT_TYPE_ID_FIELDS):
        if field in record:
            row[field] = record[field]
    rows.append(row)
    rows_by_content_id[content_id] = row
    return row


def _required_content_id(record: Mapping[str, Any]) -> str:
    for field in CONTENT_ID_FIELDS:
        value = record.get(field)
        if value not in (None, ""):
            return str(value)
    raise ValueError("record is missing contentid")
