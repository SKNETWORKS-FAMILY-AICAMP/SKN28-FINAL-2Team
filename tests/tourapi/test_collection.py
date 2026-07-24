from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from src.tourapi.crawler.collection import (
    apply_detail_record,
    collection_status,
    enrich_place_details,
    initialize_place_rows,
    merge_list_records,
    normalize_place_field_names,
    read_place_csv,
    write_place_csv,
)
from src.tourapi.preprocessing.models import PlaceRules


RULES = PlaceRules(
    preprocessing_version="test-v1",
    content_type_rules={
        "12": {"entity_type": "attraction", "target_collection": "attractions", "recommendation_scope": "default"},
        "14": {"entity_type": "culture", "target_collection": "attractions", "recommendation_scope": "default"},
        "28": {"entity_type": "activity", "target_collection": "activities", "recommendation_scope": "excluded"},
        "32": {"entity_type": "lodging", "target_collection": "lodgings", "recommendation_scope": "intent_only"},
    },
    intent_only_lcls2=frozenset(),
    overrides={
        "region": {"entity_type": "region_summary", "target_collection": "regions", "recommendation_scope": "context_only"}
    },
    excluded_content_ids={"excluded": "정책 제외"},
    dataset_rules={
        "lodging": {"entity_type": "lodging", "target_collection": "lodgings", "recommendation_scope": "intent_only"},
        "food": {"entity_type": "restaurant", "target_collection": "restaurants", "recommendation_scope": "default"},
        "leisure": {"entity_type": "activity", "target_collection": "activities", "recommendation_scope": "intent_only"},
        "shopping": {"entity_type": "shopping", "target_collection": "shopping", "recommendation_scope": "intent_only"},
    },
)


class PlaceCollectionTests(unittest.TestCase):
    def test_initializes_from_tourism_and_marks_policy_skips(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "tourism.csv"
            output = root / "places.csv"
            rows = [
                {"dataset": "tourism", "contentid": "1", "contenttypeid": "12", "title": "관광지", "common_overview": "설명", "intro_fetch_status": "success"},
                {"dataset": "tourism", "contentid": "excluded", "contenttypeid": "14", "title": "제외", "common_overview": "설명"},
                {"dataset": "tourism", "contentid": "region", "contenttypeid": "12", "title": "지역", "common_overview": "설명"},
            ]
            write_place_csv(rows, source)

            initialized = initialize_place_rows(output, source, RULES)

            self.assertEqual(initialized[0]["common_fetch_status"], "success")
            self.assertEqual(initialized[1]["intro_fetch_status"], "skipped_policy")
            self.assertEqual(initialized[2]["intro_fetch_status"], "skipped_policy")

    def test_merges_lists_and_prefers_specific_dataset_for_duplicate(self) -> None:
        rows = [{"dataset": "tourism", "contentid": "1", "contenttypeid": "32", "title": "복합시설"}]
        added = merge_list_records(
            rows,
            dataset="lodging",
            records=[
                {"contentid": "1", "contenttypeid": "32", "title": "복합시설"},
                {"contentid": "2", "contenttypeid": "32", "title": "호텔"},
            ],
        )

        self.assertEqual(added, 1)
        self.assertEqual(rows[0]["dataset"], "lodging")
        self.assertEqual(len(rows), 2)

    def test_detail_enrichment_checkpoints_and_resumes(self) -> None:
        rows = [
            {"dataset": "food", "contentid": "1", "contenttypeid": "39", "title": "식당1"},
            {"dataset": "food", "contentid": "2", "contenttypeid": "39", "title": "식당2"},
        ]

        def fake_fetcher(_key: str, **kwargs: object) -> dict[str, object]:
            return {"contentid": kwargs["content_id"], "overview": "상세 설명"}

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "places.csv"
            first_calls = enrich_place_details(
                rows,
                detail_kind="common",
                output_path=output,
                service_key="key",
                mobile_os="ETC",
                mobile_app="Test",
                call_budget=1,
                checkpoint_every=1,
                timeout=1,
                retries=1,
                fetcher=fake_fetcher,
            )
            second_calls = enrich_place_details(
                rows,
                detail_kind="common",
                output_path=output,
                service_key="key",
                mobile_os="ETC",
                mobile_app="Test",
                call_budget=1,
                checkpoint_every=1,
                timeout=1,
                retries=1,
                fetcher=fake_fetcher,
            )

            saved = read_place_csv(output)
            self.assertEqual((first_calls, second_calls), (1, 1))
            self.assertEqual(collection_status(saved).common_pending, 0)
            self.assertEqual([row["common_overview"] for row in saved], ["상세 설명", "상세 설명"])

    def test_apply_intro_detail_uses_prefixed_fields(self) -> None:
        row = {"contentid": "1", "contenttypeid": "39", "intro_old": "stale"}
        apply_detail_record(
            row,
            detail_kind="intro",
            record={"contentid": "1", "firstmenu": "갈치조림", "opentimefood": "09:00~20:00"},
        )

        self.assertNotIn("intro_old", row)
        self.assertEqual(row["intro_firstmenu"], "갈치조림")
        self.assertEqual(row["intro_fetch_status"], "success")

    def test_normalizes_case_only_duplicate_fields(self) -> None:
        rows = [
            {"common_lclsSystm1": "NA", "common_lclssystm1": ""},
            {"common_lclsSystm1": "", "common_lclssystm1": "FD"},
        ]

        normalize_place_field_names(rows)

        self.assertEqual([row["common_lclsSystm1"] for row in rows], ["NA", "FD"])
        self.assertTrue(all("common_lclssystm1" not in row for row in rows))


if __name__ == "__main__":
    unittest.main()
