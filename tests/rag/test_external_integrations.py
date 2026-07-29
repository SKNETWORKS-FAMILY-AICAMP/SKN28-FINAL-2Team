from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from src.rag.conditions import ConditionExtractionService
from src.rag.models import (
    ItineraryChoice,
    ItineraryDraft,
    PlaceSearchFilters,
    PlaceSearchResponse,
    RetrievedPlace,
    SlotCandidates,
    SlotRequest,
    TravelConditions,
)
from src.rag.operations import (
    GooglePlacesFactsProvider,
    KoreanPublicHolidayCalendar,
    OperationalFacts,
    OperationalOverrideStore,
)
from src.rag.orchestrator import RagOrchestrator
from src.rag.retrieval import SlotRetriever
from src.rag.routing import (
    FallbackRouteMetricsProvider,
    GoogleRoutesProvider,
    HaversineRouteMetricsProvider,
    KakaoMobilityRouteProvider,
    RouteProviderError,
)
from src.rag.validation import deterministic_draft, validate_and_schedule

from .test_orchestrator import FakeLLM, FakeRouteAdapter, FakeSlotRetriever


def _place(
    content_id: int,
    *,
    title: str = "검증 장소",
    latitude: float = 33.45,
    longitude: float = 126.50,
    raw: dict | None = None,
) -> RetrievedPlace:
    return RetrievedPlace(
        content_id=content_id,
        title=title,
        latitude=latitude,
        longitude=longitude,
        similarity_score=0.9,
        rank=1,
        target_collection="attractions",
        itinerary_role="visit",
        opening_hours="09:00-18:00",
        closed_days="연중무휴",
        parking="주차 가능",
        slot_score=0.9,
        raw=raw or {},
    )


def _single_slot(place: RetrievedPlace) -> SlotCandidates:
    slot = SlotRequest(
        day=1,
        sequence=1,
        role="visit",
        category="nature",
        target_collections=("attractions",),
        itinerary_roles=("visit",),
        stay_minutes=60,
        latitude=33.45,
        longitude=126.50,
        radius_km=8.0,
    )
    return SlotCandidates(slot, "자연 관광지", (place,))


class ExternalRouteProviderTests(unittest.TestCase):
    def test_kakao_parses_real_road_summary_and_coordinate_order(self) -> None:
        captured = {}

        def requester(request, timeout):
            captured["url"] = request.full_url
            captured["authorization"] = request.headers["Authorization"]
            return {
                "routes": [
                    {
                        "result_code": 0,
                        "summary": {"distance": 12340, "duration": 1260},
                    }
                ]
            }

        provider = KakaoMobilityRouteProvider(
            "test-key",
            requester=requester,
        )
        result = provider.estimate(
            (33.5104, 126.4913),
            (33.4698, 126.4930),
            transport="rental_car",
        )

        self.assertEqual(result.provider, "kakao_mobility")
        self.assertTrue(result.verified)
        self.assertAlmostEqual(result.distance_km, 12.34)
        self.assertEqual(result.duration_minutes, 21)
        self.assertIn("origin=126.4913000%2C33.5104000", captured["url"])
        self.assertEqual(captured["authorization"], "KakaoAK test-key")

    def test_google_routes_parses_distance_and_duration(self) -> None:
        captured = {}

        def requester(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["field_mask"] = request.headers["X-goog-fieldmask"]
            return {
                "routes": [
                    {"distanceMeters": 8700, "duration": "1020s"},
                ]
            }

        provider = GoogleRoutesProvider("test-key", requester=requester)
        result = provider.estimate(
            (33.5104, 126.4913),
            (33.4698, 126.4930),
            transport="rental_car",
        )

        self.assertEqual(result.provider, "google_routes")
        self.assertEqual(result.duration_minutes, 17)
        self.assertAlmostEqual(result.distance_km, 8.7)
        self.assertEqual(captured["body"]["travelMode"], "DRIVE")
        self.assertIn("routes.duration", captured["field_mask"])

    def test_provider_failure_falls_back_to_explicit_unverified_estimate(self) -> None:
        class BrokenProvider:
            def estimate(self, origin, destination, *, transport):
                raise RouteProviderError("provider unavailable")

        provider = FallbackRouteMetricsProvider(
            (BrokenProvider(),),
            fallback=HaversineRouteMetricsProvider(),
        )
        result = provider.estimate(
            (33.50, 126.49),
            (33.45, 126.55),
            transport="rental_car",
        )

        self.assertFalse(result.verified)
        self.assertEqual(result.provider, "haversine_estimate")


class OperationalFactsTests(unittest.TestCase):
    def test_google_places_extracts_closure_hours_and_accessibility(self) -> None:
        def requester(request, timeout):
            return {
                "places": [
                    {
                        "id": "places/test",
                        "businessStatus": "OPERATIONAL",
                        "currentOpeningHours": {
                            "periods": [
                                {
                                    "open": {"day": 3, "hour": 9, "minute": 0},
                                    "close": {"day": 3, "hour": 18, "minute": 0},
                                }
                            ]
                        },
                        "accessibilityOptions": {
                            "wheelchairAccessibleEntrance": True,
                            "wheelchairAccessibleRestroom": False,
                        },
                        "parkingOptions": {"freeParkingLot": True},
                    }
                ]
            }

        facts = GooglePlacesFactsProvider(
            "test-key",
            requester=requester,
        ).facts_for(_place(1), date(2026, 7, 29))

        self.assertIsNotNone(facts)
        self.assertEqual(facts.opening_ranges, ((540, 1080),))
        self.assertFalse(facts.closed_on_date)
        self.assertTrue(
            facts.accessibility["wheelchairAccessibleEntrance"]
        )
        self.assertTrue(facts.parking_options["freeParkingLot"])

    def test_versioned_override_can_mark_a_temporary_closure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "exceptions.json"
            path.write_text(
                json.dumps(
                    {
                        "place_exceptions": [
                            {
                                "content_id": 77,
                                "date": "2026-08-15",
                                "closed": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            facts = OperationalOverrideStore(path).facts_for(
                _place(77),
                date(2026, 8, 15),
            )

        self.assertIsNotNone(facts)
        self.assertTrue(facts.closed_on_date)
        self.assertEqual(facts.business_status, "CLOSED_TEMPORARILY")

    def test_external_closure_and_accessibility_failure_block_schedule(self) -> None:
        class FactsProvider:
            def facts_for(self, place, travel_date):
                return OperationalFacts(
                    source="test",
                    verified=True,
                    business_status="CLOSED_TEMPORARILY",
                    closed_on_date=True,
                    opening_ranges=((540, 1080),),
                    accessibility={
                        "wheelchairAccessibleEntrance": False,
                    },
                )

        item = _single_slot(_place(10))
        conditions = TravelConditions.from_mapping(
            {
                "start_date": "2026-07-29",
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
                "mobility_constraints": ["휠체어"],
            }
        )
        result = validate_and_schedule(
            deterministic_draft((item,), conditions),
            (item,),
            conditions,
            operational_provider=FactsProvider(),
        )

        codes = {issue.code for issue in result.issues}
        self.assertFalse(result.valid)
        self.assertIn("external_closure", codes)
        self.assertIn("accessibility_requirement_failed", codes)

    def test_public_holiday_requires_special_hours_verification(self) -> None:
        item = _single_slot(_place(11))
        conditions = TravelConditions.from_mapping(
            {
                "start_date": "2026-02-17",
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
            }
        )
        result = validate_and_schedule(
            deterministic_draft((item,), conditions),
            (item,),
            conditions,
            holiday_calendar=KoreanPublicHolidayCalendar(),
        )

        self.assertTrue(result.valid)
        self.assertIn(
            "holiday_hours_unverified",
            {warning.code for warning in result.warnings},
        )


class TourApiIdentityAndMealSearchTests(unittest.TestCase):
    def test_required_tourapi_id_is_hydrated_even_when_vector_search_misses(self) -> None:
        class PlaceService:
            def search_places(self, query, *, filters=None, **kwargs):
                return PlaceSearchResponse(
                    query,
                    filters or PlaceSearchFilters(),
                    1,
                    (_place(1, title="일반 후보"),),
                )

            def get_retrieved_places_by_ids(self, content_ids):
                return tuple(
                    _place(content_id, title="필수 장소")
                    for content_id in content_ids
                )

        slot = _single_slot(_place(1)).slot
        conditions = TravelConditions.from_mapping(
            {
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
                "must_visit_content_ids": [999],
            }
        )
        result = SlotRetriever(PlaceService()).retrieve(slot, conditions)

        self.assertIn(999, {place.content_id for place in result.candidates})
        draft = deterministic_draft((result,), conditions)
        self.assertEqual(draft.choices[0].content_id, 999)

    def test_meal_search_is_anchored_after_tourism_selection(self) -> None:
        class RecordingRetriever(FakeSlotRetriever):
            def __init__(self):
                self.meal_calls = []

            def retrieve(self, slot, conditions):
                if slot.slot_kind == "meal":
                    self.meal_calls.append(slot)
                return super().retrieve(slot, conditions)

        retriever = RecordingRetriever()
        llm = FakeLLM()
        orchestrator = RagOrchestrator(
            condition_service=ConditionExtractionService(llm),
            route_adapter=FakeRouteAdapter(),
            slot_retriever=retriever,
            llm=llm,
        )
        result = orchestrator.run(
            selected_options={
                "duration_days": 1,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
            }
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(retriever.meal_calls), 2)
        self.assertTrue(
            all(
                slot.template_source == "meal_after_tourism_selection"
                for slot in retriever.meal_calls
            )
        )
        self.assertTrue(
            all(slot.route_anchor for slot in retriever.meal_calls)
        )
        self.assertEqual(
            result["meta"]["meal_search_strategy"],
            "after_tourism_selection_radius_search",
        )


if __name__ == "__main__":
    unittest.main()
