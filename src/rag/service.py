from __future__ import annotations

import json
import math
from typing import Any, Mapping, Protocol, Sequence

from .models import (
    PlaceSearchFilters,
    PlaceSearchResponse,
    RetrievedPlace,
)


class MetadataRepository(Protocol):
    def find_rag_content_ids(self, **kwargs: Any) -> list[int]: ...

    def find_content_ids_by_titles(
        self,
        titles: Sequence[str],
        *,
        limit_per_title: int = 3,
    ) -> Mapping[str, Sequence[int]]: ...

    def get_places_by_ids(
        self,
        content_ids: Sequence[int],
    ) -> list[dict[str, Any]]: ...

    def get_aihub_evidence(
        self,
        content_ids: Sequence[int],
    ) -> dict[int, dict[str, Any]]: ...


class EmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class PlaceSearchService:
    """TourAPI vector retrieval with MySQL as the current-facts authority."""

    def __init__(
        self,
        *,
        mysql_repository: MetadataRepository,
        chroma_collection: Any,
        embedder: EmbeddingProvider,
        max_prefilter_candidates: int = 5_000,
    ) -> None:
        if max_prefilter_candidates <= 0:
            raise ValueError("max_prefilter_candidates must be greater than zero")
        self.mysql_repository = mysql_repository
        self.chroma_collection = chroma_collection
        self.embedder = embedder
        self.max_prefilter_candidates = max_prefilter_candidates

    def search_places(
        self,
        query: str,
        *,
        filters: PlaceSearchFilters | None = None,
        top_k: int = 10,
        candidate_k: int | None = None,
        include_aihub_evidence: bool = False,
        center: tuple[float, float] | None = None,
        radius_km: float | None = None,
    ) -> PlaceSearchResponse:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be blank")
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")
        filters = filters or PlaceSearchFilters()
        allowed_ids = self.mysql_repository.find_rag_content_ids(
            datasets=filters.datasets,
            target_collections=filters.target_collections,
            place_subtypes=filters.place_subtypes,
            recommendation_scopes=filters.recommendation_scopes,
            content_type_ids=filters.content_type_ids,
            cities=filters.cities,
            districts=filters.districts,
            route_eligible=filters.route_eligible,
            schedule_eligible=filters.schedule_eligible,
            requires_verification=filters.requires_verification,
            limit=self.max_prefilter_candidates,
        )
        if not allowed_ids:
            return PlaceSearchResponse(normalized_query, filters, 0, ())

        prefetched_rows: dict[int, dict[str, Any]] = {}
        if center is not None and radius_km is not None:
            if radius_km <= 0:
                raise ValueError("radius_km must be greater than zero")
            nearby_rows = self.mysql_repository.get_places_by_ids(allowed_ids)
            prefetched_rows = {
                int(row["content_id"]): dict(row)
                for row in nearby_rows
                if _row_within_radius(
                    row,
                    center=center,
                    radius_km=radius_km,
                )
            }
            allowed_ids = [
                content_id
                for content_id in allowed_ids
                if content_id in prefetched_rows
            ]
            if not allowed_ids:
                return PlaceSearchResponse(
                    normalized_query,
                    filters,
                    0,
                    (),
                )

        query_embedding = self.embedder.embed([normalized_query])
        if len(query_embedding) != 1 or not query_embedding[0]:
            raise RuntimeError("query embedder returned no embedding")
        requested_candidates = candidate_k or max(top_k * 5, 30)
        n_results = min(max(requested_candidates, top_k), len(allowed_ids))
        allowed_strings = [str(content_id) for content_id in allowed_ids]
        where = (
            {"contentid": {"$eq": allowed_strings[0]}}
            if len(allowed_strings) == 1
            else {"contentid": {"$in": allowed_strings}}
        )
        result = self.chroma_collection.query(
            query_embeddings=query_embedding,
            where=where,
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        ids = _first_result(result.get("ids"))
        distances = _first_result(result.get("distances"))
        metadatas = _first_result(result.get("metadatas"))
        documents = _first_result(result.get("documents"))
        ranked: list[tuple[int, float, Mapping[str, Any], str]] = []
        for index, document_id in enumerate(ids):
            content_id = _content_id(document_id)
            if content_id is None:
                continue
            distance = float(distances[index]) if index < len(distances) else 1.0
            metadata = (
                dict(metadatas[index] or {}) if index < len(metadatas) else {}
            )
            document = str(documents[index] or "") if index < len(documents) else ""
            ranked.append((content_id, distance, metadata, document))

        ranked_ids = [content_id for content_id, _, _, _ in ranked]
        details_by_id = {
            content_id: prefetched_rows[content_id]
            for content_id in ranked_ids
            if content_id in prefetched_rows
        }
        missing_detail_ids = [
            content_id
            for content_id in ranked_ids
            if content_id not in details_by_id
        ]
        details_by_id.update(
            {
                int(row["content_id"]): row
                for row in self.mysql_repository.get_places_by_ids(
                    missing_detail_ids
                )
            }
        )
        aihub = (
            self.mysql_repository.get_aihub_evidence(details_by_id)
            if include_aihub_evidence
            else {}
        )
        places: list[RetrievedPlace] = []
        for content_id, distance, metadata, document in ranked:
            row = details_by_id.get(content_id)
            if not row:
                continue
            place = _retrieved_place(
                row,
                metadata,
                document=document,
                rank=len(places) + 1,
                similarity=1.0 - distance,
                aihub_evidence=aihub.get(content_id),
            )
            if filters.itinerary_roles and place.itinerary_role not in set(
                filters.itinerary_roles
            ):
                continue
            places.append(place)
            if len(places) >= top_k:
                break
        return PlaceSearchResponse(
            normalized_query,
            filters,
            len(allowed_ids),
            tuple(places),
        )

    def get_places_by_ids(
        self,
        content_ids: Sequence[int],
    ) -> list[dict[str, Any]]:
        return self.mysql_repository.get_places_by_ids(content_ids)

    def get_retrieved_places_by_ids(
        self,
        content_ids: Sequence[int],
    ) -> tuple[RetrievedPlace, ...]:
        """Hydrate exact TourAPI IDs without relying on vector recall."""

        rows = self.mysql_repository.get_places_by_ids(content_ids)
        return tuple(
            _retrieved_place(
                row,
                {},
                document=str(row.get("search_text") or ""),
                rank=index,
                similarity=1.0,
                aihub_evidence=None,
            )
            for index, row in enumerate(rows, start=1)
        )

    def get_retrieved_places_by_titles(
        self,
        titles: Sequence[str],
    ) -> tuple[RetrievedPlace, ...]:
        """Resolve required place names through current MySQL TourAPI facts."""

        finder = getattr(
            self.mysql_repository,
            "find_content_ids_by_titles",
            None,
        )
        if not callable(finder):
            return ()
        matches = finder(titles)
        ordered_ids: list[int] = []
        for title in titles:
            ordered_ids.extend(int(value) for value in matches.get(title, ()))
        return self.get_retrieved_places_by_ids(
            tuple(dict.fromkeys(ordered_ids))
        )


def _first_result(value: Any) -> list[Any]:
    if not isinstance(value, list) or not value:
        return []
    first = value[0]
    return list(first) if isinstance(first, list) else []


def _content_id(document_id: Any) -> int | None:
    text = str(document_id or "").strip()
    if text.startswith("tourapi:"):
        text = text.split(":", 1)[1]
    try:
        return int(text)
    except ValueError:
        return None


def _metadata_tags(value: Any) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    if not isinstance(value, str) or not value.strip():
        return ()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return (value,)
    return (
        tuple(str(item) for item in parsed)
        if isinstance(parsed, list)
        else (value,)
    )


def _tag_value(tags: Sequence[str], prefix: str) -> str:
    marker = prefix + ":"
    return next(
        (
            tag[len(marker) :]
            for tag in tags
            if str(tag).startswith(marker)
        ),
        "",
    )


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _row_within_radius(
    row: Mapping[str, Any],
    *,
    center: tuple[float, float],
    radius_km: float,
) -> bool:
    latitude = _float(row.get("latitude"))
    longitude = _float(row.get("longitude"))
    if latitude is None or longitude is None:
        return False
    lat1, lon1 = map(math.radians, center)
    lat2, lon2 = map(math.radians, (latitude, longitude))
    delta_latitude = lat2 - lat1
    delta_longitude = lon2 - lon1
    value = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_longitude / 2) ** 2
    )
    return 6371.0 * 2 * math.asin(math.sqrt(value)) <= radius_km


def _retrieved_place(
    row: Mapping[str, Any],
    metadata: Mapping[str, Any],
    *,
    document: str,
    rank: int,
    similarity: float,
    aihub_evidence: Mapping[str, Any] | None,
) -> RetrievedPlace:
    tags = _metadata_tags(row.get("tags")) or _metadata_tags(metadata.get("tags"))
    raw = dict(row)
    raw["embedding_document"] = document
    if aihub_evidence:
        raw["aihub_mapping_evidence"] = dict(aihub_evidence)
    latitude = _float(row.get("latitude"))
    longitude = _float(row.get("longitude"))
    return RetrievedPlace(
        content_id=int(row["content_id"]),
        title=str(row.get("title") or metadata.get("title") or ""),
        latitude=latitude or 0.0,
        longitude=longitude or 0.0,
        similarity_score=round(max(-1.0, min(1.0, similarity)), 6),
        rank=rank,
        dataset=str(row.get("dataset") or metadata.get("dataset") or ""),
        target_collection=str(
            metadata.get("target_collection")
            or _tag_value(tags, "target_collection")
        ),
        itinerary_role=str(
            metadata.get("itinerary_role") or _tag_value(tags, "itinerary_role")
        ),
        tags=tags,
        address=" ".join(
            part
            for part in (
                str(row.get("addr1") or "").strip(),
                str(row.get("addr2") or "").strip(),
            )
            if part
        ),
        opening_hours=str(
            row.get("opening_hours")
            or metadata.get("opening_hours_raw")
            or ""
        ),
        closed_days=str(
            row.get("closed_days") or metadata.get("closed_days_raw") or ""
        ),
        parking=str(row.get("parking") or metadata.get("parking_raw") or ""),
        reservation=str(
            row.get("reservation") or metadata.get("reservation_raw") or ""
        ),
        use_fee=str(row.get("use_fee") or metadata.get("use_fee_raw") or ""),
        rating=_float(
            row.get("rating")
            or row.get("google_rating")
            or row.get("average_rating")
            or metadata.get("rating")
        ),
        rating_count=(
            int(rating_count)
            if (
                rating_count := _float(
                    row.get("rating_count")
                    or row.get("user_ratings_total")
                    or metadata.get("rating_count")
                )
            )
            is not None
            else None
        ),
        overview=str(row.get("overview") or document or ""),
        route_eligible=bool(row.get("route_eligible", True)),
        schedule_eligible=bool(row.get("schedule_eligible", True)),
        requires_verification=bool(row.get("requires_verification", False)),
        raw=raw,
    )
