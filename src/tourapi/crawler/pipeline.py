from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..preprocessing.models import PlaceRules
from .collection import (
    CollectionStatus,
    REMOTE_DATASETS,
    apply_tourism_intro_skips,
    collection_status,
    enrich_place_details,
    merge_list_records,
    write_place_csv,
)
from .openapi_client import (
    OPENAPI_PRESET_GROUPS,
    OpenApiDatasetPlan,
    OpenApiDatasetResult,
    OpenApiError,
    fetch_detail_common,
    fetch_detail_intro,
    fetch_openapi_dataset,
    plan_openapi_dataset,
)


MessageCallback = Callable[[str], None]
DetailProgressCallback = Callable[[str, int, int], None]
DatasetPlanner = Callable[..., OpenApiDatasetPlan]
DatasetFetcher = Callable[..., OpenApiDatasetResult]
DetailFetcher = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class CollectionOptions:
    """Runtime options shared by all stages of a resumable collection run."""

    output_path: Path
    service_key: str
    call_budget: int
    page_size: int
    checkpoint_every: int
    mobile_os: str
    mobile_app: str
    timeout: float
    retries: int

    def __post_init__(self) -> None:
        positive_values = {
            "call_budget": self.call_budget,
            "page_size": self.page_size,
            "checkpoint_every": self.checkpoint_every,
            "timeout": self.timeout,
            "retries": self.retries,
        }
        invalid = [name for name, value in positive_values.items() if value <= 0]
        if invalid:
            raise ValueError(f"collection options must be positive: {', '.join(invalid)}")
        if not self.service_key.strip():
            raise ValueError("service_key is empty")


@dataclass(frozen=True)
class CollectionServices:
    """Injectable TourAPI operations used by the pipeline."""

    plan_dataset: DatasetPlanner = plan_openapi_dataset
    fetch_dataset: DatasetFetcher = fetch_openapi_dataset
    fetch_common: DetailFetcher = fetch_detail_common
    fetch_intro: DetailFetcher = fetch_detail_intro


@dataclass(frozen=True)
class CollectionRunResult:
    status: CollectionStatus
    calls_used: int

    @property
    def complete(self) -> bool:
        return not (
            self.status.missing_datasets
            or self.status.common_pending
            or self.status.intro_pending
        )


class TourApiCollectionPipeline:
    """Collect missing lists and details while respecting one shared call budget."""

    def __init__(
        self,
        options: CollectionOptions,
        *,
        services: CollectionServices | None = None,
        on_message: MessageCallback | None = None,
        on_detail_progress: DetailProgressCallback | None = None,
    ) -> None:
        self.options = options
        self.services = services or CollectionServices()
        self.on_message = on_message
        self.on_detail_progress = on_detail_progress

    def run(
        self,
        rows: list[dict[str, Any]],
        rules: PlaceRules,
    ) -> CollectionRunResult:
        calls_used = self.collect_missing_lists(rows)
        status = collection_status(rows)
        if status.missing_datasets:
            return CollectionRunResult(status, calls_used)

        remaining = self.options.call_budget - calls_used
        if status.common_pending and remaining > 0:
            calls_used += enrich_place_details(
                rows,
                detail_kind="common",
                output_path=self.options.output_path,
                service_key=self.options.service_key,
                mobile_os=self.options.mobile_os,
                mobile_app=self.options.mobile_app,
                call_budget=remaining,
                checkpoint_every=self.options.checkpoint_every,
                timeout=self.options.timeout,
                retries=self.options.retries,
                fetcher=self.services.fetch_common,
                progress_callback=self.on_detail_progress,
            )

        apply_tourism_intro_skips(rows, rules)
        status = collection_status(rows)
        remaining = self.options.call_budget - calls_used
        if not status.common_pending and status.intro_pending and remaining > 0:
            calls_used += enrich_place_details(
                rows,
                detail_kind="intro",
                output_path=self.options.output_path,
                service_key=self.options.service_key,
                mobile_os=self.options.mobile_os,
                mobile_app=self.options.mobile_app,
                call_budget=remaining,
                checkpoint_every=self.options.checkpoint_every,
                timeout=self.options.timeout,
                retries=self.options.retries,
                fetcher=self.services.fetch_intro,
                progress_callback=self.on_detail_progress,
            )

        return CollectionRunResult(collection_status(rows), calls_used)

    def collect_missing_lists(self, rows: list[dict[str, Any]]) -> int:
        calls_used = 0
        preset_map = OPENAPI_PRESET_GROUPS["lcls"]
        missing = collection_status(rows).missing_datasets
        for dataset in REMOTE_DATASETS:
            if dataset not in missing:
                continue

            remaining = self.options.call_budget - calls_used
            if remaining < 2:
                break

            plan = self.services.plan_dataset(
                preset_map[dataset],
                service_key=self.options.service_key,
                region_mode="address",
                mobile_os=self.options.mobile_os,
                mobile_app=self.options.mobile_app,
                page_size=self.options.page_size,
                detail_mode="list",
                timeout=self.options.timeout,
                retries=self.options.retries,
            )
            if plan.planned_calls > remaining:
                calls_used += len(plan.filter_counts)
                self._emit(
                    f"[{dataset}] list needs about {plan.planned_calls} calls but only "
                    f"{remaining} remain. The count call was used; rerun with a fresh budget."
                )
                break

            result = self.services.fetch_dataset(
                plan.preset,
                service_key=self.options.service_key,
                region_mode="address",
                mobile_os=self.options.mobile_os,
                mobile_app=self.options.mobile_app,
                page_size=self.options.page_size,
                detail_mode="list",
                call_budget=remaining,
                timeout=self.options.timeout,
                retries=self.options.retries,
                plan=plan,
            )
            calls_used += result.calls_used
            if not result.base_records:
                raise OpenApiError(
                    f"{dataset} returned no Jeju records. Verify the current TourAPI "
                    "lclsSystm1 code before rerunning."
                )

            added = merge_list_records(
                rows,
                dataset=dataset,
                records=result.base_records,
            )
            write_place_csv(rows, self.options.output_path)
            self._emit(
                f"[{dataset}] Jeju records: {result.total_count}; added: {added}; "
                f"calls: {result.calls_used}"
            )
        return calls_used

    def _emit(self, message: str) -> None:
        if self.on_message is not None:
            self.on_message(message)
