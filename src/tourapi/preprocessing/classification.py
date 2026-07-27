"""TourAPI place classification rules."""

from __future__ import annotations

from typing import Any, Mapping

from .cleaner import first_value
from .models import Classification, PlaceRules


def classify_place_record(
    record: Mapping[str, Any],
    rules: PlaceRules,
) -> Classification:
    dataset = first_value(record, "dataset") or "tourism"
    if dataset == "tourism":
        return _classify_tourism_record(record, rules)

    dataset_rule = rules.dataset_rules.get(dataset)
    if dataset_rule is None:
        return Classification(
            "excluded",
            "",
            "excluded",
            exclusion_reason=f"지원하지 않는 dataset={dataset or 'blank'}",
        )
    lcls2 = first_value(record, "common_lclsSystm2", "lclsSystm2")
    subtype_rule = rules.lcls2_rules.get(lcls2, {})
    return _classification_from_rule({**dataset_rule, **subtype_rule})


def _classify_tourism_record(
    record: Mapping[str, Any],
    rules: PlaceRules,
) -> Classification:
    content_id = first_value(record, "contentid")
    excluded_reason = rules.excluded_content_ids.get(content_id)
    if excluded_reason:
        return Classification(
            "excluded", "", "excluded", exclusion_reason=excluded_reason
        )

    override = rules.overrides.get(content_id)
    if override:
        return _classification_from_rule(override)

    lcls3 = first_value(record, "lclsSystm3", "common_lclsSystm3")
    lcls3_rule = rules.tourism_lcls3_rules.get(lcls3)
    if lcls3_rule:
        return _classification_from_rule(lcls3_rule)

    content_type_id = first_value(record, "contenttypeid")
    base_rule = rules.content_type_rules.get(content_type_id)
    if base_rule is None:
        return Classification(
            "excluded",
            "",
            "excluded",
            exclusion_reason=f"지원하지 않는 contentTypeId={content_type_id or 'blank'}",
        )

    scope = str(base_rule["recommendation_scope"])
    lcls2 = first_value(record, "lclsSystm2", "common_lclsSystm2")
    if scope == "default" and lcls2 in rules.intent_only_lcls2:
        scope = "intent_only"
    if scope == "excluded":
        return Classification(
            entity_type=str(base_rule["entity_type"]),
            target_collection=str(base_rule["target_collection"]),
            recommendation_scope=scope,
            place_subtype=str(
                base_rule.get("place_subtype") or base_rule["entity_type"]
            ),
            itinerary_role=str(
                base_rule.get("itinerary_role") or base_rule["entity_type"]
            ),
            exclusion_reason=f"contentTypeId={content_type_id} 분류 정책상 제외",
        )
    return _classification_from_rule({**base_rule, "recommendation_scope": scope})


def _classification_from_rule(rule: Mapping[str, Any]) -> Classification:
    entity_type = str(rule["entity_type"])
    return Classification(
        entity_type=entity_type,
        target_collection=str(rule["target_collection"]),
        recommendation_scope=str(rule["recommendation_scope"]),
        place_subtype=str(rule.get("place_subtype") or entity_type),
        itinerary_role=str(rule.get("itinerary_role") or entity_type),
        requires_verification=bool(rule.get("requires_verification", False)),
        route_eligible_override=(
            bool(rule["route_eligible"])
            if "route_eligible" in rule
            else None
        ),
        is_itinerary_stop=bool(rule.get("is_itinerary_stop", True)),
    )
