from __future__ import annotations

import json
import unittest

from src.rag.models import PlaceSearchFilters
from src.rag.service import PlaceSearchService


class FakeRepository:
    def __init__(self, *, eligible_ids=None, rows=None, evidence=None) -> None:
        self.eligible_ids = list(eligible_ids or [])
        self.rows = list(rows or [])
        self.evidence = dict(evidence or {})
        self.filter_args = None
        self.requested_ids = []

    def find_rag_content_ids(self, **kwargs):
        self.filter_args = kwargs
        return self.eligible_ids

    def get_places_by_ids(self, content_ids):
        self.requested_ids.append(list(content_ids))
        return self.rows

    def get_aihub_evidence(self, content_ids):
        return self.evidence


class FakeEmbedder:
    model = "fake"
    dimensions = 3

    def __init__(self) -> None:
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeCollection:
    def __init__(self, result=None) -> None:
        self.result = result or {"metadatas": [[]], "distances": [[]]}
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def _row(content_id: int, title: str, *, tags='["nature"]') -> dict:
    return {
        "content_id": content_id,
        "title": title,
        "tags": tags,
        "longitude": "126.5",
        "latitude": "33.5",
        "rag_eligible": 1,
    }


class PlaceSearchServiceTests(unittest.TestCase):
    def _service(self, repository=None, collection=None, embedder=None):
        return PlaceSearchService(
            repository=repository or FakeRepository(),
            collection=collection or FakeCollection(),
            embedder=embedder or FakeEmbedder(),
        )

    def test_rejects_blank_query_and_nonpositive_top_k(self) -> None:
        service = self._service()
        with self.assertRaisesRegex(ValueError, "query must not be blank"):
            service.search_places("  ")
        with self.assertRaisesRegex(ValueError, "top_k must be greater"):
            service.search_places("제주", top_k=0)

    def test_no_eligible_ids_skips_embedding_and_vector_query(self) -> None:
        repository = FakeRepository(eligible_ids=[])
        embedder = FakeEmbedder()
        collection = FakeCollection()

        response = self._service(repository, collection, embedder).search_places("제주")

        self.assertEqual(response.places, ())
        self.assertEqual(embedder.calls, [])
        self.assertEqual(collection.calls, [])

    def test_filters_are_forwarded_and_chroma_where_is_built(self) -> None:
        repository = FakeRepository(eligible_ids=[11, 22])
        collection = FakeCollection()
        filters = PlaceSearchFilters(
            datasets=("tourapi",),
            target_collections=("attractions",),
            itinerary_roles=("visit",),
            cities=("제주시",),
            route_eligible=True,
            candidate_limit=100,
        )

        self._service(repository, collection).search_places(
            "바다",
            filters=filters,
            top_k=4,
        )

        self.assertEqual(repository.filter_args["datasets"], ("tourapi",))
        self.assertEqual(repository.filter_args["cities"], ("제주시",))
        self.assertTrue(repository.filter_args["route_eligible"])
        self.assertEqual(repository.filter_args["limit"], 100)
        self.assertEqual(
            collection.calls[0]["where"],
            {
                "$and": [
                    {"contentid": {"$in": ["11", "22"]}},
                    {"itinerary_role": {"$in": ["visit"]}},
                ]
            },
        )
        self.assertEqual(collection.calls[0]["n_results"], 4)

    def test_hydration_preserves_vector_order_deduplicates_and_drops_missing(self) -> None:
        repository = FakeRepository(
            eligible_ids=[1, 2, 3],
            rows=[_row(1, "첫째"), _row(2, "둘째")],
            evidence={2: {"visit_count": 3}},
        )
        collection = FakeCollection(
            {
                "metadatas": [[
                    {"contentid": "2"},
                    {"contentid": "1"},
                    {"contentid": "2"},
                    {"contentid": "3"},
                ]],
                "distances": [[0.1, 0.3, 0.2, 0.4]],
            }
        )

        response = self._service(repository, collection).search_places("제주")

        self.assertEqual([place.content_id for place in response.places], [2, 1])
        self.assertAlmostEqual(response.places[0].similarity_score, 0.8)
        self.assertEqual(response.places[0].aihub_evidence, {"visit_count": 3})
        self.assertEqual(repository.requested_ids, [[2, 1, 2, 3]])

    def test_invalid_vector_metadata_is_ignored(self) -> None:
        repository = FakeRepository(eligible_ids=[1], rows=[_row(1, "정상")])
        collection = FakeCollection(
            {
                "metadatas": [[None, {"contentid": "bad"}, {"contentid": "1"}]],
                "distances": [[0.1, 0.2, 0.3]],
            }
        )
        response = self._service(repository, collection).search_places("제주")
        self.assertEqual([place.content_id for place in response.places], [1])

    def test_get_places_by_ids_does_not_embed_and_has_no_similarity(self) -> None:
        repository = FakeRepository(rows=[_row(7, "직접 조회")])
        embedder = FakeEmbedder()

        places = self._service(repository, embedder=embedder).get_places_by_ids([7])

        self.assertEqual(embedder.calls, [])
        self.assertIsNone(places[0].similarity_score)
        self.assertIsNone(places[0].distance)

    def test_build_rag_context_returns_serializable_korean_json(self) -> None:
        repository = FakeRepository(eligible_ids=[1], rows=[_row(1, "협재해변")])
        collection = FakeCollection(
            {"metadatas": [[{"contentid": "1"}]], "distances": [[0.1]]}
        )

        context = self._service(repository, collection).build_rag_context("바다", top_k=1)
        payload = json.loads(context)

        self.assertEqual(payload["query"], "바다")
        self.assertEqual(payload["places"][0]["title"], "협재해변")
        self.assertEqual(payload["places"][0]["tags"], ["nature"])

    def test_invalid_tag_json_becomes_empty_list(self) -> None:
        repository = FakeRepository(rows=[_row(1, "장소", tags="not-json")])
        place = self._service(repository).get_places_by_ids([1])[0]
        self.assertEqual(place.tags, ())


if __name__ == "__main__":
    unittest.main()
