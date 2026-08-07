"""Shared normalization rules for stored package recommendation profiles."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Sequence


CATEGORY_ORDER = (
    "nature",
    "culture",
    "festival",
    "experience",
    "food",
    "cafe",
    "activity",
    "shopping",
)
PACKAGE_TAG_ORDER = ("nature", "culture", "festival", "experience")
ITEM_TAG_ORDER = ("food", "cafe", "activity", "shopping")
COMPANION_ORDER = ("solo", "friend", "couple", "family")

# TourAPI search-document tags use Korean display labels. Substring matching is
# intentional: the stored data contains values such as 체험관광 and 축제공연행사.
TAG_CATEGORY_MARKERS = {
    "자연관광": "nature",
    "문화시설": "culture",
    "축제": "festival",
    "체험": "experience",
}
PLACE_SUBTYPE_CATEGORIES = {
    "restaurant": "food",
    "cafe_tea": "cafe",
    "water_leisure": "activity",
    "land_leisure": "activity",
    "market": "shopping",
    "general_retail": "shopping",
    "local_specialty": "shopping",
}

# The old package profiles described broad party shapes rather than explicit
# relationships. Ambiguous two-person types therefore map to multiple valid
# user-facing companion groups instead of inventing a single relationship.
PACKAGE_COMPANION_ALIASES = {
    "solo": ("solo",),
    "friend": ("friend",),
    "couple": ("couple",),
    "family": ("family",),
    "non_family_two": ("friend", "couple"),
    "non_family_group": ("friend",),
    "family_two": ("couple", "family"),
    "family_group": ("family",),
    "with_children": ("family",),
    "with_parents": ("family",),
    "three_generations": ("family",),
}

# Current itinerary/RAG values remain supported while the UI moves to the four
# consolidated companion choices and eight package place categories.
CONDITION_COMPANION_ALIASES = PACKAGE_COMPANION_ALIASES
CONDITION_CATEGORY_ALIASES = {
    "nature": ("nature",),
    "history": ("culture",),
    "culture": ("culture",),
    "festival": ("festival",),
    "experience": ("experience",),
    "food": ("food",),
    "cafe": ("cafe",),
    "food_cafe": ("food", "cafe"),
    "activity": ("activity",),
    "leisure": ("activity",),
    "theme_park": ("experience", "activity"),
    "trail": ("nature",),
    "shopping": ("shopping",),
    "market_shopping": ("shopping",),
}


def categories_from_tags(tags: Iterable[str]) -> tuple[str, ...]:
    """Return all package- and item-level categories for compatibility."""

    return _ordered(
        (*package_categories_from_tags(tags), *item_categories_from_tags(tags)),
        CATEGORY_ORDER,
    )


def package_categories_from_tags(tags: Iterable[str]) -> tuple[str, ...]:
    """Map descriptive TourAPI tags to package-level travel themes."""

    categories: set[str] = set()
    for raw_tag in tags:
        tag = str(raw_tag).strip()
        if not tag:
            continue
        for marker, category in TAG_CATEGORY_MARKERS.items():
            if marker in tag:
                categories.add(category)
    return _ordered(categories, PACKAGE_TAG_ORDER)


def item_categories_from_tags(tags: Iterable[str]) -> tuple[str, ...]:
    """Map place_subtype values to categories stored on each package item."""

    categories: set[str] = set()
    for raw_tag in tags:
        tag = str(raw_tag).strip()
        if not tag:
            continue
        if tag.startswith("place_subtype:"):
            subtype = tag.split(":", 1)[1].strip().lower()
            category = PLACE_SUBTYPE_CATEGORIES.get(subtype)
            if category:
                categories.add(category)
    return _ordered(categories, ITEM_TAG_ORDER)


def build_package_profile(
    old_profile: dict[str, Any],
    item_tag_sets: Sequence[Iterable[str]],
) -> dict[str, Any]:
    """Build the new factual profile and discard old LLM themes/paces."""

    raw_companions = (
        old_profile.get("companion_types")
        or old_profile.get("party_types")
        or old_profile.get("party_type")
        or ()
    )
    companion_types = normalize_companion_types(raw_companions)
    counts: Counter[str] = Counter()
    for tags in item_tag_sets:
        counts.update(categories_from_tags(tags))
    place_categories = _ordered(counts, CATEGORY_ORDER)
    return {
        "companion_types": list(companion_types),
        "place_categories": list(place_categories),
        "category_counts": {
            category: counts[category] for category in place_categories
        },
    }


def parse_csv_values(value: Any) -> tuple[str, ...]:
    """Parse the comma-separated companion/tags DB columns."""

    if value is None:
        return ()
    return tuple(
        item.strip().lower()
        for item in str(value).split(",")
        if item.strip()
    )


def serialize_csv_values(values: Iterable[str], order: Sequence[str]) -> str:
    return ",".join(_ordered(values, order))


def normalize_companion_types(value: Any) -> tuple[str, ...]:
    values = _as_values(value)
    normalized: set[str] = set()
    for item in values:
        normalized.update(PACKAGE_COMPANION_ALIASES.get(item, ()))
    return _ordered(normalized, COMPANION_ORDER)


def normalize_condition_companions(value: Any) -> set[str]:
    normalized: set[str] = set()
    for item in _as_values(value):
        normalized.update(CONDITION_COMPANION_ALIASES.get(item, (item,)))
    return normalized


def normalize_condition_categories(value: Any) -> set[str]:
    normalized: set[str] = set()
    for item in _as_values(value):
        normalized.update(CONDITION_CATEGORY_ALIASES.get(item, (item,)))
    return normalized


def condition_category_groups(value: Any) -> tuple[frozenset[str], ...]:
    """Return one acceptable canonical-category set per user preference."""

    return tuple(
        frozenset(CONDITION_CATEGORY_ALIASES.get(item, (item,)))
        for item in _as_values(value)
    )


def _as_values(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values = (value,)
    elif isinstance(value, (list, tuple, set)):
        values = tuple(value)
    else:
        values = (value,)
    return tuple(
        str(item).strip().lower() for item in values if str(item).strip()
    )


def _ordered(values: Iterable[str], order: Sequence[str]) -> tuple[str, ...]:
    value_set = set(values)
    ordered = [item for item in order if item in value_set]
    ordered.extend(sorted(value_set - set(order)))
    return tuple(ordered)
