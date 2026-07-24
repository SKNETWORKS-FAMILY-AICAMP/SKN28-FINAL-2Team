from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
import json
from typing import Any, Protocol, Sequence

from .models import (
    PlaceSearchFilters,
    PlaceSearchResponse,
    RetrievedPlace,
    VectorCandidate,
)


class PlaceMetadataRepository(Protocol):
    def find_rag_content_ids(
        self,
        *,
        datasets: Sequence[str],
        target_collections: Sequence[str],
        place_subtypes: Sequence[str],
        recommendation_scopes: Sequence[str],
        content_type_ids: Sequence[int],
        cities: Sequence[str],
        districts: Sequence[str],
        route_eligible: bool | None,
        schedule_eligible: bool | None,
        requires_verification: bool | None,
        limit: int,
    ) -> list[int]: ...

    def get_places_by_ids(
        self, content_ids: Sequence[int]
    ) -> list[dict[str, Any]]: ...

    def get_aihub_evidence(
        self, content_ids: Sequence[int]
    ) -> dict[int, dict[str, Any]]: ...


class PlaceVectorRepository(Protocol):
    def search(
        self,
        query: str,
        *,
        allowed_content_ids: Sequence[int],
        filters: PlaceSearchFilters,
        top_k: int,
    ) -> list[VectorCandidate]: ...


class PlaceSearchService:
    """Retrieve itinerary-ready TourAPI places with current MySQL details."""

    def __init__(
        self,
        *,
        mysql_repository: PlaceMetadataRepository,
        vector_repository: PlaceVectorRepository,
        max_prefilter_candidates: int = 5_000,
    ) -> None:
        if max_prefilter_candidates <= 0:
            raise ValueError("max_prefilter_candidates must be greater than zero")
        self.mysql_repository = mysql_repository
        self.vector_repository = vector_repository
        self.max_prefilter_candidates = max_prefilter_candidates

    def search_places(
        self,
        query: str,
        *,
        filters: PlaceSearchFilters | None = None,
        top_k: int = 10,
        include_aihub_evidence: bool = True,
    ) -> PlaceSearchResponse:
        query = query.strip()
        if not query:
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
            return PlaceSearchResponse(query, filters, 0, ())

        vector_candidates = self.vector_repository.search(
            query,
            allowed_content_ids=allowed_ids,
            filters=filters,
            top_k=top_k,
        )
        ranked_ids = [candidate.content_id for candidate in vector_candidates]
        details_by_id = {
            int(row["content_id"]): row
            for row in self.mysql_repository.get_places_by_ids(ranked_ids)
        }
        evidence_by_id = (
            self.mysql_repository.get_aihub_evidence(ranked_ids)
            if include_aihub_evidence
            else {}
        )

        places: list[RetrievedPlace] = []
        for candidate in vector_candidates:
            details = details_by_id.get(candidate.content_id)
            if details is None:
                continue
            places.append(
                _retrieved_place(
                    rank=len(places) + 1,
                    candidate=candidate,
                    details=details,
                    aihub_evidence=evidence_by_id.get(candidate.content_id, {}),
                )
            )
        return PlaceSearchResponse(
            query=query,
            filters=filters,
            total_candidates=len(allowed_ids),
            places=tuple(places),
        )

    def get_places_by_ids(
        self, content_ids: Sequence[int]
    ) -> list[dict[str, Any]]:
        """Fetch the latest MySQL place facts without semantic search."""

        return self.mysql_repository.get_places_by_ids(content_ids)


def _retrieved_place(
    *,
    rank: int,
    candidate: VectorCandidate,
    details: Mapping[str, Any],
    aihub_evidence: Mapping[str, Any],
) -> RetrievedPlace:
    metadata = candidate.metadata
    address = " ".join(
        part
        for part in (
            _text(details.get("addr1")),
            _text(details.get("addr2")),
        )
        if part
    )
    return RetrievedPlace(
        rank=rank,
        content_id=candidate.content_id,
        title=_text(details.get("title") or metadata.get("title")),
        content_type=_text(details.get("content_type_name")),
        dataset=_text(details.get("dataset") or metadata.get("dataset")),
        target_collection=_text(metadata.get("target_collection")),
        place_subtype=_text(metadata.get("place_subtype")),
        itinerary_role=_text(metadata.get("itinerary_role")),
        recommendation_scope=_text(metadata.get("recommendation_scope")),
        address=address or _text(metadata.get("address")),
        longitude=_float(details.get("longitude") or metadata.get("longitude")),
        latitude=_float(details.get("latitude") or metadata.get("latitude")),
        overview=_text(details.get("overview")),
        opening_hours=_text(details.get("opening_hours")),
        closed_days=_text(details.get("closed_days")),
        parking=_text(details.get("parking")),
        reservation=_text(details.get("reservation")),
        use_fee=_text(details.get("use_fee")),
        check_in_time=_text(details.get("check_in_time")),
        check_out_time=_text(details.get("check_out_time")),
        homepage=_text(details.get("homepage")),
        image_url=_text(details.get("image_url") or metadata.get("image_url")),
        route_eligible=bool(details.get("route_eligible")),
        schedule_eligible=bool(details.get("schedule_eligible")),
        requires_verification=bool(details.get("requires_verification")),
        tags=tuple(_json_list(details.get("tags"))),
        type_details=_json_object(details.get("type_details")),
        similarity_score=candidate.similarity_score,
        distance=candidate.distance,
        retrieved_document=candidate.document,
        source_modified_at=_iso_text(details.get("source_modified_at")),
        last_fetched_at=_iso_text(details.get("last_fetched_at")),
        aihub_evidence=dict(aihub_evidence),
    )


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _json_list(value: Any) -> list[str]:
    parsed = _json_value(value, [])
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _json_object(value: Any) -> dict[str, Any]:
    parsed = _json_value(value, {})
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _iso_text(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return _text(value)
