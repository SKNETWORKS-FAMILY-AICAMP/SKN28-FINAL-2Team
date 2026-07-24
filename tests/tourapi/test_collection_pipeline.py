from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from src.tourapi.crawler.collection import collection_status, read_place_csv
from src.tourapi.crawler.openapi_client import (
    OpenApiDatasetPlan,
    OpenApiDatasetResult,
    OpenApiFilterCount,
)
from src.tourapi.crawler.pipeline import (
    CollectionOptions,
    CollectionServices,
    TourApiCollectionPipeline,
)
from src.tourapi.preprocessing.models import PlaceRules


RULES = PlaceRules(
    preprocessing_version="test-v1",
    content_type_rules={},
    intent_only_lcls2=frozenset(),
    overrides={},
    excluded_content_ids={},
    dataset_rules={},
)


def completed_rows(*, include_shopping: bool) -> list[dict[str, str]]:
    datasets = ["tourism", "lodging", "food", "leisure"]
    if include_shopping:
        datasets.append("shopping")
    return [
        {
            "dataset": dataset,
            "contentid": str(index),
            "contenttypeid": "12",
            "title": dataset,
            "common_fetch_status": "success",
            "intro_fetch_status": "success",
        }
        for index, dataset in enumerate(datasets, start=1)
    ]


class CollectionPipelineTests(unittest.TestCase):
    def options(self, output_path: Path, *, call_budget: int = 10) -> CollectionOptions:
        return CollectionOptions(
            output_path=output_path,
            service_key="test-key",
            call_budget=call_budget,
            page_size=1000,
            checkpoint_every=10,
            mobile_os="ETC",
            mobile_app="Test",
            timeout=1.0,
            retries=1,
        )

    def test_options_reject_invalid_runtime_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "call_budget"):
            self.options(Path("places.csv"), call_budget=0)

    def test_complete_checkpoint_does_not_call_remote_services(self) -> None:
        planner = Mock()
        fetcher = Mock()
        with tempfile.TemporaryDirectory() as directory:
            pipeline = TourApiCollectionPipeline(
                self.options(Path(directory) / "places.csv"),
                services=CollectionServices(
                    plan_dataset=planner,
                    fetch_dataset=fetcher,
                ),
            )
            result = pipeline.run(completed_rows(include_shopping=True), RULES)

        self.assertTrue(result.complete)
        self.assertEqual(result.calls_used, 0)
        planner.assert_not_called()
        fetcher.assert_not_called()

    def test_missing_list_is_collected_and_checkpointed(self) -> None:
        messages: list[str] = []

        def plan_dataset(preset: object, **_: object) -> OpenApiDatasetPlan:
            list_filter = preset.list_filters[0]  # type: ignore[attr-defined]
            return OpenApiDatasetPlan(
                preset=preset,  # type: ignore[arg-type]
                detail_mode="list",
                region_mode="address",
                page_size=1000,
                filter_counts=(OpenApiFilterCount(list_filter, 1),),
                planned_calls=2,
            )

        def fetch_dataset(preset: object, **_: object) -> OpenApiDatasetResult:
            return OpenApiDatasetResult(
                preset=preset,  # type: ignore[arg-type]
                filter_counts=(),
                total_count=1,
                base_records=[
                    {
                        "contentid": "99",
                        "contenttypeid": "38",
                        "title": "시장",
                    }
                ],
                common_records=[],
                intro_records=[],
                info_records=[],
                calls_used=2,
                detail_mode="list",
                region_mode="address",
                source_total_count=1,
            )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "places.csv"
            rows = completed_rows(include_shopping=False)
            pipeline = TourApiCollectionPipeline(
                self.options(output),
                services=CollectionServices(
                    plan_dataset=plan_dataset,
                    fetch_dataset=fetch_dataset,
                ),
                on_message=messages.append,
            )

            calls_used = pipeline.collect_missing_lists(rows)
            saved = read_place_csv(output)

        self.assertEqual(calls_used, 2)
        self.assertEqual(collection_status(rows).missing_datasets, ())
        self.assertEqual(saved[-1]["dataset"], "shopping")
        self.assertIn("added: 1", messages[0])

    def test_insufficient_budget_counts_plan_call_without_fetching(self) -> None:
        fetcher = Mock()

        def plan_dataset(preset: object, **_: object) -> OpenApiDatasetPlan:
            list_filter = preset.list_filters[0]  # type: ignore[attr-defined]
            return OpenApiDatasetPlan(
                preset=preset,  # type: ignore[arg-type]
                detail_mode="list",
                region_mode="address",
                page_size=1000,
                filter_counts=(OpenApiFilterCount(list_filter, 1),),
                planned_calls=3,
            )

        with tempfile.TemporaryDirectory() as directory:
            rows = completed_rows(include_shopping=False)
            pipeline = TourApiCollectionPipeline(
                self.options(Path(directory) / "places.csv", call_budget=2),
                services=CollectionServices(
                    plan_dataset=plan_dataset,
                    fetch_dataset=fetcher,
                ),
            )

            calls_used = pipeline.collect_missing_lists(rows)

        self.assertEqual(calls_used, 1)
        self.assertEqual(collection_status(rows).missing_datasets, ("shopping",))
        fetcher.assert_not_called()


if __name__ == "__main__":
    unittest.main()
