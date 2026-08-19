from __future__ import annotations

import json
from typing import Any, Sequence

from ..embeddings.embedder import OpenAIEmbeddingClient
from ..storage.mysql_repository import MySQLPlaceRepository
from .models import PlaceSearchFilters, PlaceSearchResponse, RetrievedPlace

DEFAULT_TOP_K = 8


class PlaceSearchServiceError(RuntimeError):
    """Raised when the retrieval service cannot complete a request."""


class PlaceSearchService:
    """Synchronous facade over MySQL + Chroma for the itinerary LLM team."""

    def __init__(
        self,
        *,
        repository: MySQLPlaceRepository,
        collection: Any,
        embedder: OpenAIEmbeddingClient,
    ) -> None:
        self._repository = repository
        self._collection = collection
        self._embedder = embedder

    def search_places(
        self,
        query: str,
        *,
        filters: PlaceSearchFilters | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> PlaceSearchResponse:
        if not query.strip():
            raise ValueError("query must not be blank")
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        filters = filters or PlaceSearchFilters()

        eligible_ids = self._repository.find_rag_content_ids(
            datasets=filters.datasets,
            target_collections=filters.target_collections,
            place_subtypes=filters.place_subtypes,
            recommendation_scopes=filters.recommendation_scopes,
            content_type_ids=filters.content_type_ids,
            cities=filters.cities,
            districts=filters.districts,
            region_pairs=filters.region_pairs,
            route_eligible=filters.route_eligible,
            schedule_eligible=filters.schedule_eligible,
            requires_verification=filters.requires_verification,
            limit=filters.candidate_limit,
        )
        if not eligible_ids:
            return PlaceSearchResponse(query=query, filters=filters, top_k=top_k, places=())

        embedding = self._embedder.embed([query])[0]
        where = _build_chroma_where(eligible_ids, filters.itinerary_roles)

        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where,
            include=["metadatas", "distances"],
        )
        content_ids, distances = _extract_matches(result)
        if not content_ids:
            return PlaceSearchResponse(query=query, filters=filters, top_k=top_k, places=())

        places = self._hydrate(content_ids, distances=distances)
        return PlaceSearchResponse(query=query, filters=filters, top_k=top_k, places=tuple(places))

    def get_places_by_ids(self, content_ids: Sequence[int]) -> list[RetrievedPlace]:
        """Look up place details directly, without calling the embedding API."""

        return self._hydrate(list(content_ids), distances=None)

    def build_rag_context(
        self,
        query: str,
        *,
        filters: PlaceSearchFilters | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> str:
        """Return a JSON string suitable for inclusion in an LLM prompt."""

        response = self.search_places(query, filters=filters, top_k=top_k)
        return json.dumps(response.to_dict(), ensure_ascii=False)

    def _hydrate(
        self,
        content_ids: Sequence[int],
        *,
        distances: dict[int, float] | None,
    ) -> list[RetrievedPlace]:
        if not content_ids:
            return []

        rows = self._repository.get_places_by_ids(content_ids)
        rows_by_id = {int(row["content_id"]): row for row in rows}
        evidence_by_id = self._repository.get_aihub_evidence(content_ids)

        ordered_ids = list(dict.fromkeys(int(value) for value in content_ids))
        places: list[RetrievedPlace] = []
        for content_id in ordered_ids:
            row = rows_by_id.get(content_id)
            if row is None:
                # MySQL is the source of truth; drop candidates it no longer knows about.
                continue
            distance = None if distances is None else distances.get(content_id)
            similarity_score = None if distance is None else 1.0 - distance
            places.append(
                _place_from_row(
                    row,
                    similarity_score=similarity_score,
                    distance=distance,
                    aihub_evidence=evidence_by_id.get(content_id),
                )
            )
        return places


def _build_chroma_where(
    eligible_ids: Sequence[int], itinerary_roles: Sequence[str]
) -> dict[str, Any]:
    conditions: list[dict[str, Any]] = [
        {"contentid": {"$in": [str(content_id) for content_id in eligible_ids]}}
    ]
    if itinerary_roles:
        conditions.append({"itinerary_role": {"$in": list(itinerary_roles)}})
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _extract_matches(result: Any) -> tuple[list[int], dict[int, float]]:
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    content_ids: list[int] = []
    distance_by_id: dict[int, float] = {}
    for metadata, distance in zip(metadatas, distances, strict=False):
        raw_content_id = (metadata or {}).get("contentid")
        try:
            content_id = int(raw_content_id)
        except (TypeError, ValueError):
            continue
        content_ids.append(content_id)
        distance_by_id[content_id] = float(distance)
    return content_ids, distance_by_id


def _place_from_row(
    row: dict[str, Any],
    *,
    similarity_score: float | None,
    distance: float | None,
    aihub_evidence: dict[str, Any] | None,
) -> RetrievedPlace:
    return RetrievedPlace(
        content_id=int(row["content_id"]),
        title=str(row.get("title") or ""),
        content_type_id=_optional_int(row.get("content_type_id")),
        content_type_name=row.get("content_type_name"),
        lcls3_code=row.get("lcls3_code"),
        lcls1_name=row.get("lcls1_name"),
        lcls2_name=row.get("lcls2_name"),
        lcls3_name=row.get("lcls3_name"),
        addr1=row.get("addr1"),
        addr2=row.get("addr2"),
        longitude=_optional_float(row.get("longitude")),
        latitude=_optional_float(row.get("latitude")),
        tel=row.get("tel"),
        tel_name=row.get("tel_name"),
        homepage=row.get("homepage"),
        overview=row.get("overview"),
        info_center=row.get("info_center"),
        opening_hours=row.get("opening_hours"),
        closed_days=row.get("closed_days"),
        parking=row.get("parking"),
        reservation=row.get("reservation"),
        use_fee=row.get("use_fee"),
        check_in_time=row.get("check_in_time"),
        check_out_time=row.get("check_out_time"),
        type_details=row.get("type_details"),
        dataset=row.get("dataset"),
        rag_eligible=_optional_bool(row.get("rag_eligible")),
        route_eligible=_optional_bool(row.get("route_eligible")),
        schedule_eligible=_optional_bool(row.get("schedule_eligible")),
        requires_verification=_optional_bool(row.get("requires_verification")),
        search_text=row.get("search_text"),
        tags=tuple(_parse_tags(row.get("tags"))),
        preprocessing_version=row.get("preprocessing_version"),
        generated_at=row.get("generated_at"),
        image_url=row.get("image_url"),
        source_modified_at=row.get("source_modified_at"),
        last_fetched_at=row.get("last_fetched_at"),
        similarity_score=similarity_score,
        distance=distance,
        aihub_evidence=aihub_evidence,
    )


def _parse_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_bool(value: Any) -> bool | None:
    return None if value is None else bool(value)
