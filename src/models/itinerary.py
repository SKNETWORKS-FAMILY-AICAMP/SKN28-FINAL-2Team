from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .travel_condition import TravelCondition


@dataclass
class SlotCandidate:
    content_id: int
    title: str
    final_score: float
    similarity_score: float | None
    place: dict[str, Any]
    forced: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_id": self.content_id,
            "title": self.title,
            "final_score": self.final_score,
            "similarity_score": self.similarity_score,
            "place": self.place,
            "forced": self.forced,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SlotCandidate":
        return cls(
            content_id=data["content_id"],
            title=data["title"],
            final_score=data["final_score"],
            similarity_score=data.get("similarity_score"),
            place=data.get("place", {}),
            forced=data.get("forced", False),
        )


@dataclass
class ItinerarySlot:
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
    
    @classmethod
    def from_dict(cls, data: dict) -> "ItinerarySlot":
        return cls(
            day=data["day"],
            sequence=data["sequence"],
            role=data["role"],
            target_collections=tuple(data["target_collections"]),
            itinerary_roles=tuple(data["itinerary_roles"]),
            stay_minutes=data.get("stay_minutes"),
            location_hint=data.get("location_hint"),
            query=data.get("query", ""),
            candidates=[
                SlotCandidate.from_dict(c)
                for c in data.get("candidates", [])
            ],
        )

    

@dataclass
class ItineraryState:
    condition: TravelCondition
    slots: list[ItinerarySlot]
    itinerary: dict[str, Any]
    used_content_ids: set[int] = field(default_factory=set)
    recommendations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition": self.condition.to_llm_dict(),
            "slots": [slot.to_dict() for slot in self.slots],
            "itinerary": self.itinerary,
            "used_content_ids": sorted(self.used_content_ids),
            "recommendations": self.recommendations,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
    ) -> "ItineraryState":

        return cls(
            condition=TravelCondition.from_mapping(
                data["condition"]
            ),
            slots=[
                ItinerarySlot.from_dict(slot)
                for slot in data["slots"]
            ],
            itinerary=data["itinerary"],
            used_content_ids=set(
                data.get("used_content_ids", [])
            ),
            recommendations=data.get(
                "recommendations",
                [],
            ),
        )