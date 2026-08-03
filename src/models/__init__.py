"""Shared data models for the itinerary pipeline."""

from .itinerary import ItinerarySlot, ItineraryState, SlotCandidate
from .travel_condition import (
    ConditionDelta,
    LocalTransport,
    Pace,
    PartyType,
    TravelCondition,
    VisitPreference,
    apply_delta,
    infer_affected_slots,
)

__all__ = [
    "ConditionDelta",
    "ItinerarySlot",
    "ItineraryState",
    "LocalTransport",
    "Pace",
    "PartyType",
    "SlotCandidate",
    "TravelCondition",
    "VisitPreference",
    "apply_delta",
    "infer_affected_slots",
]
