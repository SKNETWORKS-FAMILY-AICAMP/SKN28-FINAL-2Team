"""CSV I/O for AIHub recommendation candidate filtering."""

from __future__ import annotations

import csv
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

from .mapping_export import EXPORT_COLUMNS
from .recommendation_filter import (
    AUDIT_COLUMNS,
    FranchiseRules,
    NonTourismRules,
    RecommendationFilterSummary,
    build_recommendation_filter,
)


def create_recommendation_csvs(
    input_path: str | Path,
    output_path: str | Path,
    excluded_output_path: str | Path,
    franchise_rules_path: str | Path,
    non_tourism_rules_path: str | Path,
) -> RecommendationFilterSummary:
    """Read the mapping export and atomically write kept and excluded rows."""

    source = Path(input_path).resolve()
    destination = Path(output_path).resolve()
    excluded_destination = Path(excluded_output_path).resolve()
    if destination == excluded_destination:
        raise ValueError("output and excluded output paths must differ")

    rows = read_mapping_csv(source)
    franchise_rules = load_franchise_rules(franchise_rules_path)
    non_tourism_rules = load_non_tourism_rules(non_tourism_rules_path)
    result = build_recommendation_filter(rows, franchise_rules, non_tourism_rules)
    output_columns = (*EXPORT_COLUMNS, *AUDIT_COLUMNS)
    write_csv_atomic(destination, output_columns, result.recommendations)
    write_csv_atomic(
        excluded_destination,
        (*output_columns, "exclusion_reason"),
        result.exclusions,
    )
    return result.summary


def read_mapping_csv(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"mapping CSV does not exist: {source}")
    with source.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = tuple(reader.fieldnames or ())
        missing = set(EXPORT_COLUMNS).difference(fieldnames)
        if missing:
            raise ValueError(
                "mapping CSV is missing required columns: " + ", ".join(sorted(missing))
            )
        rows = list(reader)
    if not rows:
        raise ValueError("mapping CSV contains no data rows")
    return rows


def load_franchise_rules(path: str | Path) -> FranchiseRules:
    rules_path = Path(path)
    if not rules_path.exists():
        raise FileNotFoundError(f"franchise rules do not exist: {rules_path}")
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("franchise rules must contain a JSON object")
    return FranchiseRules.from_payload(payload)


def load_non_tourism_rules(path: str | Path) -> NonTourismRules:
    rules_path = Path(path)
    if not rules_path.exists():
        raise FileNotFoundError(f"non-tourism rules do not exist: {rules_path}")
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("non-tourism rules must contain a JSON object")
    return NonTourismRules.from_payload(payload)


def write_csv_atomic(
    path: str | Path,
    fieldnames: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    destination = Path(path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8-sig",
            newline="",
            dir=destination.parent,
            prefix=f".{destination.stem}-",
            suffix=".tmp",
            delete=False,
        ) as csv_file:
            temporary_path = Path(csv_file.name)
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        temporary_path.replace(destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def summary_payload(summary: RecommendationFilterSummary) -> dict[str, int]:
    return {key: int(value) for key, value in asdict(summary).items()}
