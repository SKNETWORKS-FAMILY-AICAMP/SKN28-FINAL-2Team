from __future__ import annotations

from collections import Counter
from pathlib import Path
import csv
import tempfile
import unittest

from src.common.paths import TOURAPI_DATA_ROOT, TOURAPI_SCRIPTS_ROOT
from src.tourapi.crawler.collection import (
    initialize_place_rows,
    write_place_csv,
)
from src.tourapi.preprocessing.cleaner import (
    clean_text,
    parse_address,
    validated_coordinates,
)
from src.tourapi.preprocessing.deduplication import group_duplicate_places
from src.tourapi.preprocessing.models import PlaceRules
from src.tourapi.preprocessing.preprocessing import (
    build_place_vector_document,
    classify_place_record,
    load_place_rules,
    preprocess_place_csv,
)


RULES = PlaceRules(
    preprocessing_version="places-test-v1",
    content_type_rules={
        "12": {"entity_type": "attraction", "target_collection": "attractions", "recommendation_scope": "default"},
        "14": {"entity_type": "culture", "target_collection": "attractions", "recommendation_scope": "default"},
        "28": {"entity_type": "activity", "target_collection": "activities", "recommendation_scope": "excluded"},
        "32": {"entity_type": "lodging", "target_collection": "lodgings", "recommendation_scope": "default"},
    },
    intent_only_lcls2=frozenset({"VE09", "VE12"}),
    overrides={
        "region": {"entity_type": "region_summary", "target_collection": "regions", "recommendation_scope": "context_only", "route_eligible": False, "is_itinerary_stop": False}
    },
    excluded_content_ids={"excluded": "정책 제외"},
    dataset_rules={
        "lodging": {"entity_type": "lodging", "place_subtype": "lodging", "itinerary_role": "stay", "target_collection": "lodgings", "recommendation_scope": "default"},
        "food": {"entity_type": "restaurant", "place_subtype": "restaurant", "itinerary_role": "meal", "target_collection": "restaurants", "recommendation_scope": "default"},
        "leisure": {"entity_type": "activity", "place_subtype": "leisure", "itinerary_role": "activity", "target_collection": "activities", "recommendation_scope": "intent_only"},
        "shopping": {"entity_type": "shopping", "place_subtype": "shopping", "itinerary_role": "shopping", "target_collection": "shopping", "recommendation_scope": "intent_only"},
    },
    lcls2_rules={
        "FD01": {"entity_type": "restaurant", "place_subtype": "restaurant", "itinerary_role": "meal"},
        "FD05": {"entity_type": "cafe", "place_subtype": "cafe_tea", "itinerary_role": "cafe_break"},
        "LS01": {"place_subtype": "land_leisure", "itinerary_role": "activity"},
        "LS02": {"place_subtype": "water_leisure", "itinerary_role": "activity"},
        "LS04": {"place_subtype": "complex_leisure", "itinerary_role": "activity"},
        "SH04": {"place_subtype": "general_retail", "itinerary_role": "shopping", "recommendation_scope": "intent_only"},
        "SH05": {"place_subtype": "local_specialty", "itinerary_role": "shopping", "recommendation_scope": "intent_only"},
        "SH06": {"entity_type": "market", "place_subtype": "market", "itinerary_role": "market_visit", "recommendation_scope": "default"},
        "SH07": {"place_subtype": "local_specialty", "itinerary_role": "shopping", "recommendation_scope": "intent_only"},
    },
)


def base_record(dataset: str, content_type_id: str, lcls1: str) -> dict[str, str]:
    return {
        "dataset": dataset,
        "contentid": "1",
        "contenttypeid": content_type_id,
        "title": "테스트 장소",
        "common_title": "테스트 장소",
        "common_overview": "제주 여행 장소에 대한 설명",
        "common_addr1": "제주특별자치도 제주시 조천읍 테스트로 1",
        "common_mapx": "126.5",
        "common_mapy": "33.4",
        "common_lclsSystm1": lcls1,
        "common_fetch_status": "success",
        "intro_fetch_status": "success",
    }


class PlacePreprocessingTests(unittest.TestCase):
    def test_cleaners_normalize_html_address_and_coordinates(self) -> None:
        self.assertEqual(clean_text("<p>제주&nbsp;설명<br>두 번째 줄</p>"), "제주 설명 두 번째 줄")
        self.assertEqual(
            parse_address("제주특별자치도 서귀포시 안덕면 산록남로 786"),
            ("서귀포시", "안덕면"),
        )
        self.assertEqual(validated_coordinates("126.5", "33.4"), (126.5, 33.4))
        self.assertEqual(validated_coordinates("12.7", "33.4"), (None, None))

    def test_tourism_policy_excludes_and_routes_region_context(self) -> None:
        excluded = {**base_record("tourism", "14", "VE"), "contentid": "excluded"}
        region = {**base_record("tourism", "12", "VE"), "contentid": "region"}

        self.assertFalse(classify_place_record(excluded, RULES).is_indexable)
        region_document = build_place_vector_document(
            region, classify_place_record(region, RULES), "places-test-v1"
        )
        self.assertEqual(region_document["metadata"]["target_collection"], "regions")
        self.assertFalse(region_document["metadata"]["route_eligible"])
        self.assertFalse(region_document["metadata"]["is_itinerary_stop"])

    def test_food_menu_is_embedded_and_hours_are_metadata(self) -> None:
        record = {
            **base_record("food", "39", "FD"),
            "intro_firstmenu": "갈치조림",
            "intro_treatmenu": "고등어구이, 전복죽",
            "intro_opentimefood": "09:00~20:00",
            "intro_restdatefood": "매주 화요일",
            "intro_parkingfood": "주차 가능",
            "intro_reservationfood": "전화 예약",
        }
        classification = classify_place_record(record, RULES)
        document = build_place_vector_document(record, classification, "places-test-v1")

        self.assertEqual(document["metadata"]["target_collection"], "restaurants")
        self.assertEqual(document["metadata"]["place_subtype"], "restaurant")
        self.assertEqual(document["metadata"]["itinerary_role"], "meal")
        self.assertIn("대표 메뉴: 갈치조림", document["embedding_text"])
        self.assertNotIn("09:00~20:00", document["embedding_text"])
        self.assertEqual(document["metadata"]["opening_hours_raw"], "09:00~20:00")
        self.assertEqual(document["metadata"]["reservation_raw"], "전화 예약")

    def test_address_preserves_addr1_addr2_and_combined_value(self) -> None:
        record = {
            **base_record("tourism", "12", "NA"),
            "common_addr2": "관광안내소 2층",
        }
        document = build_place_vector_document(
            record, classify_place_record(record, RULES), "places-test-v1"
        )

        self.assertEqual(
            document["metadata"]["addr1"],
            "제주특별자치도 제주시 조천읍 테스트로 1",
        )
        self.assertEqual(document["metadata"]["addr2"], "관광안내소 2층")
        self.assertEqual(
            document["metadata"]["address"],
            "제주특별자치도 제주시 조천읍 테스트로 1 관광안내소 2층",
        )

    def test_shopping_and_leisure_use_intent_only_scope(self) -> None:
        shopping = {
            **base_record("shopping", "38", "SH"),
            "common_lclsSystm2": "SH04",
            "intro_saleitem": "제주 특산품",
            "intro_shopguide": "1층 식품관",
            "intro_opentime": "10:00~19:00",
        }
        leisure = {
            **base_record("leisure", "28", "LS"),
            "common_lclsSystm2": "LS02",
            "intro_sports": "카약",
            "intro_usetimeleports": "10:00~18:00",
        }

        shopping_doc = build_place_vector_document(
            shopping, classify_place_record(shopping, RULES), "places-test-v1"
        )
        leisure_doc = build_place_vector_document(
            leisure, classify_place_record(leisure, RULES), "places-test-v1"
        )

        self.assertEqual(shopping_doc["metadata"]["recommendation_scope"], "intent_only")
        self.assertEqual(shopping_doc["metadata"]["place_subtype"], "general_retail")
        self.assertIn("판매 품목: 제주 특산품", shopping_doc["embedding_text"])
        self.assertEqual(leisure_doc["metadata"]["recommendation_scope"], "intent_only")
        self.assertEqual(leisure_doc["metadata"]["place_subtype"], "water_leisure")
        self.assertIn("레저 종목: 카약", leisure_doc["embedding_text"])

    def test_food_cafe_and_market_receive_distinct_itinerary_roles(self) -> None:
        cafe = {
            **base_record("food", "39", "FD"),
            "common_lclsSystm2": "FD05",
        }
        market = {
            **base_record("shopping", "38", "SH"),
            "common_lclsSystm2": "SH06",
        }

        cafe_classification = classify_place_record(cafe, RULES)
        market_classification = classify_place_record(market, RULES)
        cafe_document = build_place_vector_document(
            cafe, cafe_classification, "places-test-v1"
        )
        market_document = build_place_vector_document(
            market, market_classification, "places-test-v1"
        )

        self.assertEqual(cafe_classification.entity_type, "cafe")
        self.assertEqual(cafe_classification.place_subtype, "cafe_tea")
        self.assertEqual(cafe_classification.itinerary_role, "cafe_break")
        self.assertIn("카페/찻집", cafe_document["embedding_text"])
        self.assertEqual(market_classification.entity_type, "market")
        self.assertEqual(market_classification.place_subtype, "market")
        self.assertEqual(market_classification.itinerary_role, "market_visit")
        self.assertEqual(market_classification.recommendation_scope, "default")
        self.assertIn("시장", market_document["embedding_text"])

    def test_lodging_uses_check_in_time_for_schedule(self) -> None:
        lodging = {
            **base_record("lodging", "32", "AC"),
            "intro_checkintime": "15:00",
            "intro_checkouttime": "11:00",
            "intro_roomtype": "더블룸, 패밀리룸",
        }
        document = build_place_vector_document(
            lodging, classify_place_record(lodging, RULES), "places-test-v1"
        )

        self.assertTrue(document["metadata"]["schedule_eligible"])
        self.assertIn("객실 유형: 더블룸, 패밀리룸", document["embedding_text"])

    def test_blank_overview_does_not_abort_preprocessing(self) -> None:
        record = {
            **base_record("shopping", "38", "SH"),
            "common_overview": "",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            unified = Path(temp_dir) / "places.csv"
            write_place_csv([record], unified)
            result = preprocess_place_csv(unified, RULES)

        self.assertEqual(len(result.documents), 1)
        document = result.documents[0]
        self.assertFalse(document["metadata"]["overview_available"])
        self.assertNotIn("설명:", document["embedding_text"])

    def test_actual_tourism_data_applies_current_policy_results(self) -> None:
        rules = load_place_rules(TOURAPI_SCRIPTS_ROOT / "configs" / "place_rules.json")
        source = (
            TOURAPI_DATA_ROOT
            / "raw"
            / "korea_tour_openapi_jeju_lcls_address_tourism.csv"
        )
        if not source.exists():
            self.skipTest("TourAPI tourism seed CSV is not available")
        with tempfile.TemporaryDirectory() as temp_dir:
            unified = Path(temp_dir) / "places.csv"
            rows = initialize_place_rows(unified, source, rules)
            write_place_csv(rows, unified)
            result = preprocess_place_csv(unified, rules)

        self.assertEqual(len(rows), 674)
        self.assertEqual(len(result.documents), 649)
        self.assertEqual(result.excluded_count, 25)
        self.assertEqual(
            result.collection_counts,
            {"activities": 2, "attractions": 647},
        )

    def test_actual_tourism_rules_exclude_complexes_and_classify_resorts_as_lodging(
        self,
    ) -> None:
        rules = load_place_rules(TOURAPI_SCRIPTS_ROOT / "configs" / "place_rules.json")
        source = (
            TOURAPI_DATA_ROOT
            / "raw"
            / "korea_tour_openapi_jeju_lcls_address_tourism.csv"
        )
        if not source.exists():
            self.skipTest("TourAPI tourism seed CSV is not available")
        with source.open(encoding="utf-8-sig", newline="") as csv_file:
            rows_by_content_id = {
                row["contentid"]: row for row in csv.DictReader(csv_file)
            }

        resort_rows = [
            row
            for row in rows_by_content_id.values()
            if (row.get("common_lclsSystm3") or row.get("lclsSystm3"))
            == "VE050200"
        ]
        self.assertEqual(len(resort_rows), 17)
        for row in resort_rows:
            classification = classify_place_record(row, rules)
            self.assertEqual(classification.entity_type, "lodging")
            self.assertEqual(classification.place_subtype, "lodging")
            self.assertEqual(classification.itinerary_role, "stay")
            self.assertEqual(classification.target_collection, "lodgings")
            self.assertFalse(classification.is_indexable)

        aquana = classify_place_record(rows_by_content_id["600584"], rules)
        self.assertEqual(aquana.entity_type, "attraction")
        self.assertEqual(aquana.target_collection, "attractions")

        for content_id in ("127492", "1957971"):
            classification = classify_place_record(rows_by_content_id[content_id], rules)
            self.assertFalse(classification.is_indexable)

    def test_actual_related_facilities_are_added_to_document_metadata(self) -> None:
        rules = load_place_rules(TOURAPI_SCRIPTS_ROOT / "configs" / "place_rules.json")
        source = (
            TOURAPI_DATA_ROOT / "raw" / "korea_tour_openapi_jeju_places.csv"
        )
        if not source.exists():
            self.skipTest("unified TourAPI collection CSV is not available")
        result = preprocess_place_csv(source, rules)
        documents = {
            document["metadata"]["contentid"]: document
            for document in result.documents
        }

        aquana = documents["600584"]["metadata"]

        self.assertNotIn("138185", documents)
        self.assertNotIn("2796937", documents)
        self.assertNotIn("2876795", documents)
        self.assertEqual(aquana["parent_contentid"], "138185")
        self.assertEqual(
            aquana["related_places"],
            [
                {
                    "contentid": "138185",
                    "relationship_type": "onsite_activity",
                    "relation_role": "child",
                }
            ],
        )
        self.assertEqual(len(result.place_relationships), 2)

    def test_groups_same_venue_and_merges_all_secondary_records_from_rag(self) -> None:
        tourism = {
            **base_record("tourism", "12", "VE"),
            "contentid": "100",
            "title": "테스트 테마파크",
            "common_title": "테스트 테마파크",
        }
        onsite_shop = {
            **base_record("shopping", "38", "SH"),
            "contentid": "200",
            "title": "테스트 테마파크",
            "common_title": "테스트 테마파크",
        }
        duplicate_shop_primary = {
            **base_record("shopping", "38", "SH"),
            "contentid": "300",
            "title": "같은 기념품점",
            "common_title": "같은 기념품점",
        }
        duplicate_shop_secondary = {
            **base_record("shopping", "38", "SH"),
            "contentid": "301",
            "title": "같은 기념품점",
            "common_title": "같은 기념품점",
        }
        rows = [tourism, onsite_shop, duplicate_shop_primary, duplicate_shop_secondary]
        grouping = group_duplicate_places(rows)

        self.assertEqual(len(grouping.groups), 2)
        self.assertEqual(
            grouping.memberships["200"].relationship_type, "onsite_shopping"
        )
        self.assertEqual(
            grouping.memberships["301"].relationship_type, "exact_duplicate"
        )

        onsite_document = build_place_vector_document(
            onsite_shop,
            classify_place_record(onsite_shop, RULES),
            "places-test-v1",
            group_membership=grouping.memberships["200"],
        )
        self.assertFalse(onsite_document["metadata"]["is_itinerary_stop"])
        self.assertEqual(
            onsite_document["metadata"]["canonical_contentid"], "100"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            unified = Path(temp_dir) / "places.csv"
            write_place_csv(rows, unified)
            result = preprocess_place_csv(unified, RULES)

        self.assertEqual(len(result.documents), 2)
        documents = {
            document["metadata"]["contentid"]: document
            for document in result.documents
        }
        self.assertEqual(documents["100"]["metadata"]["merged_contentids"], ["200"])
        self.assertEqual(
            result.excluded_by_reason[
                "대표 장소에 병합된 중복 장소 (onsite_shopping)"
            ],
            1,
        )
        self.assertEqual(
            result.excluded_by_reason[
                "대표 장소에 병합된 중복 장소 (exact_duplicate)"
            ],
            1,
        )

    def test_groups_qualified_titles_and_configured_aliases(self) -> None:
        primary = {
            **base_record("tourism", "12", "VE"),
            "contentid": "100",
            "title": "생각하는 정원",
            "common_title": "생각하는 정원",
        }
        qualified = {
            **base_record("shopping", "38", "SH"),
            "contentid": "200",
            "title": "생각하는 정원[면세점(TAX REFUND SHOP)]",
            "common_title": "생각하는 정원[면세점(TAX REFUND SHOP)]",
        }
        alias = {
            **base_record("tourism", "12", "VE"),
            "contentid": "300",
            "title": "용두암해안도로",
            "common_title": "용두암해안도로",
        }
        alias_primary = {
            **base_record("tourism", "12", "VE"),
            "contentid": "301",
            "title": "용담해안도로",
            "common_title": "용담해안도로",
        }

        grouping = group_duplicate_places(
            [primary, qualified, alias, alias_primary],
            title_aliases={"용두암해안도로": "용담해안도로"},
        )

        self.assertEqual(len(grouping.groups), 2)
        self.assertEqual(grouping.memberships["200"].canonical_content_id, "100")
        self.assertEqual(grouping.memberships["300"].canonical_content_id, "301")

    def test_current_unified_data_has_expected_duplicate_groups(self) -> None:
        unified = (
            TOURAPI_DATA_ROOT / "raw" / "korea_tour_openapi_jeju_places.csv"
        )
        if not unified.exists():
            self.skipTest("unified collection has not been created yet")
        with unified.open(encoding="utf-8-sig", newline="") as csv_file:
            rows = list(csv.DictReader(csv_file))

        rules = load_place_rules(TOURAPI_SCRIPTS_ROOT / "configs" / "place_rules.json")
        grouping = group_duplicate_places(rows, title_aliases=rules.title_aliases)
        relationships = [
            member.relationship_type
            for group in grouping.groups
            for member in group.members
            if not member.is_primary_place
        ]

        self.assertEqual(len(grouping.groups), 14)
        self.assertEqual(relationships.count("onsite_shopping"), 7)
        self.assertEqual(relationships.count("exact_duplicate"), 8)


    def test_current_unified_data_matches_subtype_distribution(self) -> None:
        unified = (
            TOURAPI_DATA_ROOT / "raw" / "korea_tour_openapi_jeju_places.csv"
        )
        if not unified.exists():
            self.skipTest("unified collection has not been created yet")
        rules = load_place_rules(TOURAPI_SCRIPTS_ROOT / "configs" / "place_rules.json")
        with unified.open(encoding="utf-8-sig", newline="") as csv_file:
            rows = list(csv.DictReader(csv_file))

        subtype_counts = Counter(
            classify_place_record(row, rules).place_subtype
            for row in rows
            if row["dataset"] in {"food", "leisure", "shopping"}
        )

        self.assertEqual(subtype_counts["restaurant"], 492)
        self.assertEqual(subtype_counts["cafe_tea"], 230)
        self.assertEqual(subtype_counts["land_leisure"], 86)
        self.assertEqual(subtype_counts["water_leisure"], 23)
        self.assertEqual(subtype_counts["complex_leisure"], 4)
        self.assertEqual(subtype_counts["general_retail"], 343)
        self.assertEqual(subtype_counts["local_specialty"], 32)
        self.assertEqual(subtype_counts["market"], 20)


if __name__ == "__main__":
    unittest.main()
