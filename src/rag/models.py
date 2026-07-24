from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Any, Iterable


def _normalized_strings(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))


@dataclass(frozen=True)
class PlaceSearchFilters:
    """Structured constraints applied before semantic place search.

    TourAPI lodging documents use the ``intent_only`` recommendation scope.
    Callers searching for lodging should therefore pass
    ``recommendation_scopes=("intent_only",)``.
    """

    datasets: tuple[str, ...] = ()
    target_collections: tuple[str, ...] = ()
    place_subtypes: tuple[str, ...] = ()
    itinerary_roles: tuple[str, ...] = ()
    recommendation_scopes: tuple[str, ...] = ("default",)
    content_type_ids: tuple[int, ...] = ()
    cities: tuple[str, ...] = ()
    districts: tuple[str, ...] = ()
    route_eligible: bool | None = None
    schedule_eligible: bool | None = None
    requires_verification: bool | None = False

    def __post_init__(self) -> None:
        for field_name in (
            "datasets",
            "target_collections",
            "place_subtypes",
            "itinerary_roles",
            "recommendation_scopes",
            "cities",
            "districts",
        ):
            object.__setattr__(
                self,
                field_name,
                _normalized_strings(getattr(self, field_name)),
            )
        object.__setattr__(
            self,
            "content_type_ids",
            tuple(dict.fromkeys(int(value) for value in self.content_type_ids)),
        )


@dataclass(frozen=True)
class VectorCandidate:
    content_id: int
    document_id: str
    distance: float
    similarity_score: float
    document: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievedPlace:
    rank: int
    content_id: int
    title: str
    content_type: str
    dataset: str
    target_collection: str
    place_subtype: str
    itinerary_role: str
    recommendation_scope: str
    address: str
    longitude: float
    latitude: float
    overview: str
    opening_hours: str
    closed_days: str
    parking: str
    reservation: str
    use_fee: str
    check_in_time: str
    check_out_time: str
    homepage: str
    image_url: str
    route_eligible: bool
    schedule_eligible: bool
    requires_verification: bool
    tags: tuple[str, ...]
    type_details: dict[str, Any]
    similarity_score: float
    distance: float
    retrieved_document: str
    source_modified_at: str
    last_fetched_at: str
    aihub_evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tags"] = list(self.tags)
        return payload

    def to_context_dict(self) -> dict[str, Any]:
        """Return a compact, prompt-safe representation for an itinerary LLM."""

        return {
            "content_id": self.content_id,
            "title": self.title,
            "category": {
                "content_type": self.content_type,
                "dataset": self.dataset,
                "target_collection": self.target_collection,
                "place_subtype": self.place_subtype,
                "itinerary_role": self.itinerary_role,
            },
            "location": {
                "address": self.address,
                "longitude": self.longitude,
                "latitude": self.latitude,
            },
            "operation": {
                "opening_hours": self.opening_hours,
                "closed_days": self.closed_days,
                "parking": self.parking,
                "reservation": self.reservation,
                "use_fee": self.use_fee,
                "check_in_time": self.check_in_time,
                "check_out_time": self.check_out_time,
                "schedule_eligible": self.schedule_eligible,
                "requires_verification": self.requires_verification,
            },
            "description": self.overview[:800],
            "tags": list(self.tags),
            "retrieval": {
                "rank": self.rank,
                "similarity_score": round(self.similarity_score, 6),
            },
            "aihub_evidence": self.aihub_evidence,
            "source": {
                "homepage": self.homepage,
                "image_url": self.image_url,
                "source_modified_at": self.source_modified_at,
                "last_fetched_at": self.last_fetched_at,
            },
        }


@dataclass(frozen=True)
class PlaceSearchResponse:
    query: str
    filters: PlaceSearchFilters
    total_candidates: int
    places: tuple[RetrievedPlace, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "filters": asdict(self.filters),
            "total_candidates": self.total_candidates,
            "result_count": len(self.places),
            "places": [place.to_dict() for place in self.places],
        }

    def to_context_json(self, *, indent: int | None = 2) -> str:
        """Serialize retrieved facts for direct insertion into an LLM prompt."""

        payload = {
            "query": self.query,
            "result_count": len(self.places),
            "places": [place.to_context_dict() for place in self.places],
        }
        return json.dumps(payload, ensure_ascii=False, indent=indent)
