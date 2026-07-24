from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

@dataclass(frozen=True)
class Classification:
    entity_type: str
    target_collection: str
    recommendation_scope: str
    place_subtype: str = ""
    itinerary_role: str = ""
    requires_verification: bool = False
    route_eligible_override: bool | None = None
    is_itinerary_stop: bool = True
    exclusion_reason: str | None = None

    @property
    def is_indexable(self) -> bool:
        return self.recommendation_scope != "excluded" and self.exclusion_reason is None


@dataclass(frozen=True)
class PlaceRelationship:
    parent_content_id: str
    child_content_id: str
    relationship_type: str


@dataclass(frozen=True)
class PlaceRules:
    preprocessing_version: str
    content_type_rules: Mapping[str, Mapping[str, Any]]
    intent_only_lcls2: frozenset[str]
    overrides: Mapping[str, Mapping[str, Any]]
    excluded_content_ids: Mapping[str, str]
    dataset_rules: Mapping[str, Mapping[str, Any]]
    lcls2_rules: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    tourism_lcls3_rules: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    place_relationships: tuple[PlaceRelationship, ...] = ()
    title_aliases: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PlaceGroupMember:
    content_id: str
    dataset: str
    place_group_id: str
    canonical_content_id: str
    relationship_type: str
    is_primary_place: bool


@dataclass(frozen=True)
class PlaceGroup:
    place_group_id: str
    canonical_content_id: str
    normalized_title: str
    members: tuple[PlaceGroupMember, ...]


@dataclass(frozen=True)
class PlaceGroupingResult:
    groups: tuple[PlaceGroup, ...]
    memberships: Mapping[str, PlaceGroupMember]


@dataclass(frozen=True)
class PlacePreprocessResult:
    documents: list[dict[str, Any]]
    source_record_count: int
    excluded_count: int
    excluded_by_reason: dict[str, int]
    dataset_counts: dict[str, int]
    collection_counts: dict[str, int]
    scope_counts: dict[str, int]
    subtype_counts: dict[str, int]
    itinerary_role_counts: dict[str, int]
    route_ineligible_count: int
    preprocessing_version: str
    place_groups: tuple[PlaceGroup, ...] = ()
    place_relationships: tuple[PlaceRelationship, ...] = ()
