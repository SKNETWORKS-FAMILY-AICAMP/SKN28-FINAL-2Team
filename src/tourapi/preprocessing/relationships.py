from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .models import PlaceRelationship


@dataclass(frozen=True)
class RelatedPlace:
    content_id: str
    relationship_type: str
    relation_role: str


def parse_place_relationships(value: Any) -> tuple[PlaceRelationship, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("place_relationships must be a list")

    relationships: list[PlaceRelationship] = []
    seen: set[tuple[str, str, str]] = set()
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("each place relationship must be an object")
        parent_content_id = str(item.get("parent_contentid") or "").strip()
        child_content_id = str(item.get("child_contentid") or "").strip()
        relationship_type = str(item.get("relationship_type") or "").strip()
        if not parent_content_id or not child_content_id or not relationship_type:
            raise ValueError(
                "place relationships require parent_contentid, child_contentid, "
                "and relationship_type"
            )
        if parent_content_id == child_content_id:
            raise ValueError("a place relationship cannot reference itself")
        key = (parent_content_id, child_content_id, relationship_type)
        if key in seen:
            raise ValueError(f"duplicate place relationship: {key}")
        seen.add(key)
        relationships.append(
            PlaceRelationship(
                parent_content_id=parent_content_id,
                child_content_id=child_content_id,
                relationship_type=relationship_type,
            )
        )
    return tuple(relationships)


def index_place_relationships(
    relationships: Sequence[PlaceRelationship],
) -> dict[str, tuple[RelatedPlace, ...]]:
    indexed: dict[str, list[RelatedPlace]] = defaultdict(list)
    for relationship in relationships:
        indexed[relationship.parent_content_id].append(
            RelatedPlace(
                content_id=relationship.child_content_id,
                relationship_type=relationship.relationship_type,
                relation_role="parent",
            )
        )
        indexed[relationship.child_content_id].append(
            RelatedPlace(
                content_id=relationship.parent_content_id,
                relationship_type=relationship.relationship_type,
                relation_role="child",
            )
        )
    return {
        content_id: tuple(
            sorted(
                related_places,
                key=lambda item: (
                    item.relationship_type,
                    item.relation_role,
                    item.content_id,
                ),
            )
        )
        for content_id, related_places in indexed.items()
    }


def related_places_payload(
    related_places: Sequence[RelatedPlace],
) -> list[dict[str, str]]:
    return [
        {
            "contentid": related.content_id,
            "relationship_type": related.relationship_type,
            "relation_role": related.relation_role,
        }
        for related in related_places
    ]


def place_relationships_payload(
    relationships: Sequence[PlaceRelationship],
) -> list[dict[str, str]]:
    return [
        {
            "parent_contentid": relationship.parent_content_id,
            "child_contentid": relationship.child_content_id,
            "relationship_type": relationship.relationship_type,
        }
        for relationship in relationships
    ]
