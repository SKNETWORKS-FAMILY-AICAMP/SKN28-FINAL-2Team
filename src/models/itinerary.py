from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .travel_condition import TravelCondition


@dataclass
class SlotCandidate:
    """One RAG/Planner candidate offered to the LLM for a single slot."""

    content_id: int
    title: str
    final_score: float
    similarity_score: float | None
    place: dict[str, Any]
    forced: bool = False
    """True when this candidate was injected because the traveller explicitly
    asked for it (TravelCondition.must_visit_places), rather than because it
    ranked highly in Planner's search-based scoring. The itinerary-generation
    prompt is instructed to always include forced candidates."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_id": self.content_id,
            "title": self.title,
            "final_score": self.final_score,
            "similarity_score": self.similarity_score,
            "place": self.place,
            "forced": self.forced,
        }


@dataclass
class ItinerarySlot:
    """One AIHub-structure slot (a single stop) plus its search candidates."""

    day: int
    sequence: int
    role: str
    target_collections: tuple[str, ...]
    itinerary_roles: tuple[str, ...]
    stay_minutes: int | None
    location_hint: dict[str, float] | None
    query: str = ""
    candidates: list[SlotCandidate] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "sequence": self.sequence,
            "role": self.role,
            "target_collections": list(self.target_collections),
            "itinerary_roles": list(self.itinerary_roles),
            "stay_minutes": self.stay_minutes,
            "location_hint": self.location_hint,
            "query": self.query,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


@dataclass
class ItineraryState:
    """Everything the engine needs to keep editing one itinerary."""

    condition: TravelCondition
    slots: list[ItinerarySlot]
    itinerary: dict[str, Any]
    used_content_ids: set[int] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition": self.condition.to_llm_dict(),
            "slots": [slot.to_dict() for slot in self.slots],
            "itinerary": self.itinerary,
            "used_content_ids": sorted(self.used_content_ids),
        }
