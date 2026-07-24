from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import unittest
from typing import Any, Iterator

from src.config.settings import ChromaConfig, MySQLConfig
from src.rag.models import PlaceSearchFilters, VectorCandidate
from src.rag.service import PlaceSearchService
from src.rag.vector_store import ChromaPlaceRepository
from src.storage.mysql_repository import MySQLPlaceRepository


class FakeEmbedder:
    model = "text-embedding-3-small"
    dimensions = 3

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeCollection:
    name = "jeju_places"
    metadata = {
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 3,
    }

    def __init__(self) -> None:
        self.query_kwargs: dict[str, Any] = {}

    def query(self, **kwargs: Any) -> dict[str, Any]:
        self.query_kwargs = kwargs
        return {
            "ids": [["tourapi:10"]],
            "documents": [["가족 실내 체험 장소"]],
            "metadatas": [[{
                "contentid": "10",
                "title": "테스트 장소",
                "dataset": "tourism",
                "target_collection": "attractions",
                "place_subtype": "experience",
                "itinerary_role": "visit",
                "recommendation_scope": "default",
            }]],
            "distances": [[0.2]],
        }


class FakeChromaClient:
    def __init__(self, collection: FakeCollection) -> None:
        self.collection = collection

    def list_collections(self) -> list[FakeCollection]:
        return [self.collection]

    def get_collection(
        self, name: str, embedding_function: Any = None
    ) -> FakeCollection:
        return self.collection


class VectorRepositoryTests(unittest.TestCase):
    def test_search_uses_prefilter_ids_and_structured_metadata(self) -> None:
        collection = FakeCollection()
        config = ChromaConfig(
            mode="persistent",
            collection_name="jeju_places",
            persist_directory=Path("data/vectorstore"),
            host="127.0.0.1",
            port=8000,
            ssl=False,
            openai_api_key="not-a-real-key",
        )
        repository = ChromaPlaceRepository(
            config,
            embedder=FakeEmbedder(),
            client=FakeChromaClient(collection),
        )

        candidates = repository.search(
            "아이와 실내 체험",
            allowed_content_ids=[10, 20],
            filters=PlaceSearchFilters(
                target_collections=("attractions",),
                itinerary_roles=("visit",),
                schedule_eligible=True,
            ),
            top_k=5,
        )

        self.assertEqual(candidates[0].content_id, 10)
        self.assertAlmostEqual(candidates[0].similarity_score, 0.8)
        self.assertEqual(collection.query_kwargs["query_embeddings"], [[0.1, 0.2, 0.3]])
        self.assertEqual(collection.query_kwargs["n_results"], 2)
        where_text = json.dumps(
            collection.query_kwargs["where"], ensure_ascii=False
        )
        self.assertIn("contentid", where_text)
        self.assertIn("target_collection", where_text)
        self.assertIn("schedule_eligible", where_text)


class FakeMySQLRepository:
    def __init__(self) -> None:
        self.prefilter_kwargs: dict[str, Any] = {}

    def find_rag_content_ids(self, **kwargs: Any) -> list[int]:
        self.prefilter_kwargs = kwargs
        return [10, 20]

    def get_places_by_ids(
        self, content_ids: list[int]
    ) -> list[dict[str, Any]]:
        return [{
            "content_id": 10,
            "title": "테스트 장소",
            "content_type_name": "관광지",
            "dataset": "tourism",
            "addr1": "제주특별자치도 제주시",
            "addr2": "",
            "longitude": 126.5,
            "latitude": 33.5,
            "overview": "가족이 방문하기 좋은 실내 체험 장소",
            "opening_hours": "09:00~18:00",
            "closed_days": "월요일",
            "parking": "가능",
            "reservation": "",
            "use_fee": "성인 10,000원",
            "check_in_time": "",
            "check_out_time": "",
            "homepage": "https://example.com",
            "image_url": "https://example.com/image.jpg",
            "route_eligible": True,
            "schedule_eligible": True,
            "requires_verification": False,
            "tags": '["실내", "가족"]',
            "type_details": '{"kids_facility": "있음"}',
            "source_modified_at": "2026-07-20T00:00:00",
            "last_fetched_at": "2026-07-24T00:00:00",
        }]

    def get_aihub_evidence(
        self, content_ids: list[int]
    ) -> dict[int, dict[str, Any]]:
        return {10: {"visit_count": 12, "average_satisfaction": 4.5}}


class FakeVectorRepository:
    def search(self, query: str, **kwargs: Any) -> list[VectorCandidate]:
        return [
            VectorCandidate(
                content_id=10,
                document_id="tourapi:10",
                distance=0.1,
                similarity_score=0.9,
                document="가족 실내 체험",
                metadata={
                    "dataset": "tourism",
                    "target_collection": "attractions",
                    "place_subtype": "experience",
                    "itinerary_role": "visit",
                    "recommendation_scope": "default",
                },
            )
        ]


class PlaceSearchServiceTests(unittest.TestCase):
    def test_service_combines_vector_rank_with_current_mysql_facts(self) -> None:
        mysql = FakeMySQLRepository()
        service = PlaceSearchService(
            mysql_repository=mysql,
            vector_repository=FakeVectorRepository(),
        )
        filters = PlaceSearchFilters(schedule_eligible=True)

        response = service.search_places(
            "아이와 실내 체험",
            filters=filters,
            top_k=5,
        )

        self.assertEqual(response.total_candidates, 2)
        self.assertEqual(response.places[0].title, "테스트 장소")
        self.assertEqual(response.places[0].opening_hours, "09:00~18:00")
        self.assertEqual(response.places[0].aihub_evidence["visit_count"], 12)
        self.assertTrue(mysql.prefilter_kwargs["schedule_eligible"])
        context = json.loads(response.to_context_json())
        self.assertEqual(context["places"][0]["content_id"], 10)
        self.assertNotIn("retrieved_document", context["places"][0])

    def test_service_skips_embedding_when_prefilter_is_empty(self) -> None:
        mysql = FakeMySQLRepository()
        mysql.find_rag_content_ids = lambda **kwargs: []
        service = PlaceSearchService(
            mysql_repository=mysql,
            vector_repository=FakeVectorRepository(),
        )

        response = service.search_places("없는 조건")

        self.assertEqual(response.places, ())
        self.assertEqual(response.total_candidates, 0)


class RecordingCursor:
    def __init__(self) -> None:
        self.sql = ""
        self.parameters: tuple[Any, ...] = ()

    def execute(self, sql: str, parameters: tuple[Any, ...]) -> None:
        self.sql = sql
        self.parameters = parameters

    def fetchall(self) -> list[tuple[int]]:
        return [(10,), (20,)]

    def close(self) -> None:
        pass


class RecordingConnection:
    def __init__(self, cursor: RecordingCursor) -> None:
        self._cursor = cursor

    def cursor(self, **kwargs: Any) -> RecordingCursor:
        return self._cursor


class RecordingMySQLRepository(MySQLPlaceRepository):
    def __init__(self, cursor: RecordingCursor) -> None:
        super().__init__(
            MySQLConfig(
                host="127.0.0.1",
                port=3306,
                user="test",
                password="secret",
                database="test",
            )
        )
        self.cursor = cursor

    @contextmanager
    def connect(self, *, include_database: bool = True) -> Iterator[Any]:
        yield RecordingConnection(self.cursor)


class MySQLRetrievalTests(unittest.TestCase):
    def test_prefilter_builds_parameterized_tag_and_flag_filters(self) -> None:
        cursor = RecordingCursor()
        repository = RecordingMySQLRepository(cursor)

        ids = repository.find_rag_content_ids(
            target_collections=("lodgings",),
            recommendation_scopes=("intent_only",),
            schedule_eligible=True,
            requires_verification=False,
            limit=100,
        )

        self.assertEqual(ids, [10, 20])
        self.assertIn("JSON_CONTAINS(sd.tags, %s)", cursor.sql)
        self.assertIn("sd.schedule_eligible = %s", cursor.sql)
        self.assertIn('"target_collection:lodgings"', cursor.parameters)
        self.assertIn('"recommendation_scope:intent_only"', cursor.parameters)
        self.assertEqual(cursor.parameters[-1], 100)


if __name__ == "__main__":
    unittest.main()
