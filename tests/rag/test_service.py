from __future__ import annotations

import unittest

from src.rag.models import PlaceSearchFilters
from src.rag.service import PlaceSearchService


class FakeMySQL:
    def __init__(self) -> None:
        self.requested_ids = []

    def find_rag_content_ids(self, **kwargs):
        return [101, 102]

    def find_content_ids_by_titles(self, titles, *, limit_per_title=3):
        return {
            title: [101] if title == "TourAPI 자연 장소" else []
            for title in titles
        }

    def get_places_by_ids(self, content_ids):
        self.requested_ids = list(content_ids)
        return [
            {
                "content_id": 101,
                "title": "TourAPI 자연 장소",
                "latitude": 33.45,
                "longitude": 126.50,
                "dataset": "tourism",
                "route_eligible": True,
                "schedule_eligible": True,
                "requires_verification": False,
                "opening_hours": "09:00-18:00",
                "closed_days": "연중무휴",
                "parking": "가능",
                "reservation": "",
                "use_fee": "무료",
                "overview": "현재 MySQL 상세 설명",
                "addr1": "제주특별자치도 제주시",
                "addr2": "",
                "tags": '["target_collection:attractions", "itinerary_role:visit"]',
            }
        ]

    def get_aihub_evidence(self, content_ids):
        raise AssertionError("route RAG must not require AIHub place mappings")


class FakeCollection:
    def __init__(self) -> None:
        self.where = None

    def query(self, **kwargs):
        self.where = kwargs["where"]
        return {
            "ids": [["tourapi:101"]],
            "distances": [[0.2]],
            "metadatas": [
                [
                    {
                        "title": "과거 벡터 제목",
                        "target_collection": "attractions",
                        "itinerary_role": "visit",
                    }
                ]
            ],
            "documents": [["벡터 검색 문서"]],
        }


class FakeEmbedder:
    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


class PlaceSearchServiceTests(unittest.TestCase):
    def test_geographic_prefilter_runs_before_vector_query(self) -> None:
        class GeoMySQL(FakeMySQL):
            def get_places_by_ids(self, content_ids):
                self.requested_ids = list(content_ids)
                rows = {
                    101: {
                        "content_id": 101,
                        "title": "가까운 식당",
                        "latitude": 33.45,
                        "longitude": 126.50,
                        "dataset": "tourism",
                        "route_eligible": True,
                        "schedule_eligible": True,
                        "requires_verification": False,
                        "tags": (
                            '["target_collection:restaurants", '
                            '"itinerary_role:meal"]'
                        ),
                    },
                    102: {
                        "content_id": 102,
                        "title": "먼 식당",
                        "latitude": 33.10,
                        "longitude": 126.10,
                        "dataset": "tourism",
                        "route_eligible": True,
                        "schedule_eligible": True,
                        "requires_verification": False,
                        "tags": (
                            '["target_collection:restaurants", '
                            '"itinerary_role:meal"]'
                        ),
                    },
                }
                return [
                    rows[content_id]
                    for content_id in content_ids
                    if content_id in rows
                ]

        class GeoCollection(FakeCollection):
            def query(self, **kwargs):
                result = super().query(**kwargs)
                result["metadatas"][0][0].update(
                    {
                        "target_collection": "restaurants",
                        "itinerary_role": "meal",
                    }
                )
                return result

        mysql = GeoMySQL()
        chroma = GeoCollection()
        service = PlaceSearchService(
            mysql_repository=mysql,
            chroma_collection=chroma,
            embedder=FakeEmbedder(),
        )

        result = service.search_places(
            "가까운 점심 식당",
            filters=PlaceSearchFilters(
                target_collections=("restaurants",),
                itinerary_roles=("meal",),
            ),
            top_k=5,
            center=(33.45, 126.50),
            radius_km=8.0,
        )

        self.assertEqual(
            chroma.where,
            {"contentid": {"$eq": "101"}},
        )
        self.assertEqual(result.total_candidates, 1)
        self.assertEqual(
            [place.content_id for place in result.places],
            [101],
        )

    def test_prefilters_chroma_and_hydrates_current_mysql_facts(self) -> None:
        mysql = FakeMySQL()
        chroma = FakeCollection()
        service = PlaceSearchService(
            mysql_repository=mysql,
            chroma_collection=chroma,
            embedder=FakeEmbedder(),
        )

        result = service.search_places(
            "부모님과 자연 관광",
            filters=PlaceSearchFilters(
                target_collections=("attractions",),
                itinerary_roles=("visit",),
            ),
            top_k=5,
        )

        self.assertEqual(mysql.requested_ids, [101])
        self.assertEqual(
            chroma.where,
            {"contentid": {"$in": ["101", "102"]}},
        )
        self.assertEqual(len(result.places), 1)
        self.assertEqual(result.places[0].title, "TourAPI 자연 장소")
        self.assertEqual(result.places[0].overview, "현재 MySQL 상세 설명")
        self.assertAlmostEqual(result.places[0].similarity_score, 0.8)

    def test_resolves_required_title_from_mysql_when_vector_misses(self) -> None:
        service = PlaceSearchService(
            mysql_repository=FakeMySQL(),
            chroma_collection=FakeCollection(),
            embedder=FakeEmbedder(),
        )

        places = service.get_retrieved_places_by_titles(
            ["TourAPI 자연 장소"]
        )

        self.assertEqual(len(places), 1)
        self.assertEqual(places[0].content_id, 101)
        self.assertEqual(places[0].title, "TourAPI 자연 장소")


if __name__ == "__main__":
    unittest.main()
