from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Sequence


@dataclass(frozen=True)
class PlaceSearchFilters:
    """Deterministic constraints applied before semantic search.

    ``target_collections``, ``place_subtypes`` and ``recommendation_scopes``
    are matched against MySQL's ``place_search_documents.tags`` column.
    ``itinerary_roles`` is matched against the Chroma metadata for each
    candidate, since it is not part of the MySQL tag set.
    """

    target_collections: Sequence[str] = ()
    itinerary_roles: Sequence[str] = ()
    place_subtypes: Sequence[str] = ()
    recommendation_scopes: Sequence[str] = ()
    datasets: Sequence[str] = ()
    content_type_ids: Sequence[int] = ()
    cities: Sequence[str] = ()
    districts: Sequence[str] = ()
    route_eligible: bool | None = None
    schedule_eligible: bool | None = None
    requires_verification: bool | None = None
    candidate_limit: int = 2_000

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievedPlace:
    """A single place returned by :class:`PlaceSearchService`.

    Descriptive fields (address, opening hours, fees, ...) always come from
    MySQL, which is the source of truth for up-to-date place details. Only
    ``similarity_score``/``distance`` come from the Chroma vector search and
    are ``None`` when the place was looked up by id instead of by query.
    """

    content_id: int
    title: str
    content_type_id: int | None = None
    content_type_name: str | None = None
    lcls3_code: str | None = None
    lcls1_name: str | None = None
    lcls2_name: str | None = None
    lcls3_name: str | None = None
    addr1: str | None = None
    addr2: str | None = None
    longitude: float | None = None
    latitude: float | None = None
    tel: str | None = None
    tel_name: str | None = None
    homepage: str | None = None
    overview: str | None = None
    info_center: str | None = None
    opening_hours: str | None = None
    closed_days: str | None = None
    parking: str | None = None
    reservation: str | None = None
    use_fee: str | None = None
    check_in_time: str | None = None
    check_out_time: str | None = None
    type_details: str | None = None
    dataset: str | None = None
    rag_eligible: bool | None = None
    route_eligible: bool | None = None
    schedule_eligible: bool | None = None
    requires_verification: bool | None = None
    search_text: str | None = None
    tags: tuple[str, ...] = ()
    preprocessing_version: str | None = None
    generated_at: Any = None
    image_url: str | None = None
    source_modified_at: Any = None
    last_fetched_at: Any = None
    similarity_score: float | None = None
    distance: float | None = None
    aihub_evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tags"] = list(self.tags)
        for key in ("generated_at", "source_modified_at", "last_fetched_at"):
            payload[key] = _serialize_datetime(payload.get(key))
        return payload


@dataclass(frozen=True)
class PlaceSearchResponse:
    """Result of a semantic place search, ready for API responses."""

    query: str
    filters: PlaceSearchFilters
    top_k: int
    places: tuple[RetrievedPlace, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "top_k": self.top_k,
            "filters": self.filters.to_dict(),
            "places": [place.to_dict() for place in self.places],
        }


def _serialize_datetime(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value
