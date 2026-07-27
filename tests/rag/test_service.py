from __future__ import annotations

import unittest

from src.rag.models import PlaceSearchFilters
from src.rag.service import PlaceSearchService


class FakeMySQL:
    def __init__(self) -> None:
        self.requested_ids = []

    def find_rag_content_ids(self, **kwargs):
        return [101, 102]

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


if __name__ == "__main__":
    unittest.main()
