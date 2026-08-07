from __future__ import annotations

from enum import Enum


class PartyType(str, Enum):
    SOLO = "solo"
    NON_FAMILY_TWO = "non_family_two"
    NON_FAMILY_GROUP = "non_family_group"
    FAMILY_TWO = "family_two"
    FAMILY_GROUP = "family_group"
    WITH_CHILDREN = "with_children"
    WITH_PARENTS = "with_parents"
    THREE_GENERATIONS = "three_generations"


class LocalTransport(str, Enum):
    RENTAL_CAR = "rental_car"
    OWN_CAR = "own_car"
    PUBLIC_TRANSIT = "public_transit"
    TAXI = "taxi"
    MIXED = "mixed"


class VisitPreference(str, Enum):
    NATURE = "nature"
    HISTORY = "history"
    CULTURE = "culture"
    MARKET_SHOPPING = "market_shopping"
    LEISURE = "leisure"
    THEME_PARK = "theme_park"
    TRAIL = "trail"
    FESTIVAL = "festival"
    FOOD_CAFE = "food_cafe"
    EXPERIENCE = "experience"


class Pace(str, Enum):
    RELAXED = "relaxed"
    BALANCED = "balanced"
    PACKED = "packed"