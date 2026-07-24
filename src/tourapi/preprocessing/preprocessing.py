from __future__ import annotations

from collections import Counter
import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .classification import classify_place_record
from .cleaner import (
    clean_text,
    extract_first_url,
    first_value,
    parse_address,
    validated_coordinates,
)
from .deduplication import group_duplicate_places, place_groups_payload
from .models import (
    Classification,
    PlaceGroupMember,
    PlacePreprocessResult,
    PlaceRules,
)
from .relationships import (
    RelatedPlace,
    index_place_relationships,
    parse_place_relationships,
    place_relationships_payload,
    related_places_payload,
)


CONTENT_TYPE_LABELS = {
    "12": "관광지",
    "14": "문화시설",
    "28": "레저스포츠",
    "32": "숙박",
    "38": "쇼핑",
    "39": "음식점",
}
LCLS1_LABELS = {
    "NA": "자연관광",
    "HS": "역사관광",
    "EX": "체험관광",
    "VE": "문화관광",
    "AC": "숙박",
    "FD": "음식",
    "LS": "레저스포츠",
    "SH": "쇼핑",
}
PLACE_SUBTYPE_LABELS = {
    "restaurant": "음식점",
    "cafe_tea": "카페/찻집",
    "land_leisure": "육상 레저",
    "water_leisure": "수상 레저",
    "complex_leisure": "복합 레저",
    "general_retail": "일반 쇼핑",
    "local_specialty": "특산품/기념품점",
    "market": "시장",
}
OPENING_HOURS_FIELDS = (
    "intro_usetime",
    "intro_usetimeculture",
    "intro_usetimeleports",
    "intro_opentimefood",
    "intro_opentime",
)
CLOSED_DAYS_FIELDS = (
    "intro_restdate",
    "intro_restdateculture",
    "intro_restdateleports",
    "intro_restdatefood",
    "intro_restdateshopping",
)
PARKING_FIELDS = (
    "intro_parking",
    "intro_parkingculture",
    "intro_parkingleports",
    "intro_parkinglodging",
    "intro_parkingfood",
    "intro_parkingshopping",
)
INFO_CENTER_FIELDS = (
    "intro_infocenter",
    "intro_infocenterculture",
    "intro_infocenterleports",
    "intro_infocenterlodging",
    "intro_infocenterfood",
    "intro_infocentershopping",
)
USE_FEE_FIELDS = ("intro_usefee", "intro_usefeeleports")
EXPERIENCE_AGE_FIELDS = ("intro_expagerange", "intro_expagerangeleports")
RESERVATION_FIELDS = (
    "intro_reservation",
    "intro_reservationlodging",
    "intro_reservationurl",
    "intro_reservationfood",
)
BABY_CARRIAGE_FIELDS = (
    "intro_chkbabycarriage",
    "intro_chkbabycarriageculture",
    "intro_chkbabycarriageleports",
    "intro_chkbabycarriageshopping",
)
PET_FIELDS = (
    "intro_chkpet",
    "intro_chkpetculture",
    "intro_chkpetleports",
    "intro_chkpetshopping",
)
CREDIT_CARD_FIELDS = (
    "intro_chkcreditcard",
    "intro_chkcreditcardculture",
    "intro_chkcreditcardleports",
    "intro_chkcreditcardfood",
    "intro_chkcreditcardshopping",
)


def load_place_rules(path: str | Path) -> PlaceRules:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PlaceRules(
        preprocessing_version=str(payload["place_preprocessing_version"]),
        content_type_rules=payload["content_type_rules"],
        intent_only_lcls2=frozenset(
            str(code) for code in payload.get("intent_only_lcls2", [])
        ),
        overrides=payload.get("overrides", {}),
        excluded_content_ids=payload.get("excluded_content_ids", {}),
        dataset_rules=payload["dataset_rules"],
        lcls2_rules=payload.get("lcls2_rules", {}),
        tourism_lcls3_rules=payload.get("tourism_lcls3_rules", {}),
        place_relationships=parse_place_relationships(
            payload.get("place_relationships")
        ),
        title_aliases={
            str(alias): str(canonical)
            for alias, canonical in payload.get("title_aliases", {}).items()
        },
    )


def preprocess_place_csv(input_path: str | Path, rules: PlaceRules) -> PlacePreprocessResult:
    with Path(input_path).open(encoding="utf-8-sig", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))
    _validate_source_rows(rows)
    grouping = group_duplicate_places(rows, title_aliases=rules.title_aliases)
    rows_by_content_id = {
        first_value(row, "contentid", "contentId"): row for row in rows
    }
    group_aliases: dict[str, tuple[str, ...]] = {}
    merged_content_ids: dict[str, tuple[str, ...]] = {}
    for group in grouping.groups:
        canonical_row = rows_by_content_id[group.canonical_content_id]
        canonical_title = clean_text(
            first_value(canonical_row, "common_title", "title")
        )
        group_aliases[group.canonical_content_id] = tuple(
            sorted(
                {
                    clean_text(
                        first_value(
                            rows_by_content_id[member.content_id],
                            "common_title",
                            "title",
                        )
                    )
                    for member in group.members
                    if member.content_id != group.canonical_content_id
                    and clean_text(
                        first_value(
                            rows_by_content_id[member.content_id],
                            "common_title",
                            "title",
                        )
                    )
                    != canonical_title
                }
            )
        )
        merged_content_ids[group.canonical_content_id] = tuple(
            member.content_id
            for member in group.members
            if member.content_id != group.canonical_content_id
        )
    source_content_ids = {first_value(row, "contentid") for row in rows}
    active_relationships = tuple(
        relationship
        for relationship in rules.place_relationships
        if relationship.parent_content_id in source_content_ids
        and relationship.child_content_id in source_content_ids
    )
    relationship_index = index_place_relationships(active_relationships)

    documents: list[dict[str, Any]] = []
    excluded_reasons: Counter[str] = Counter()
    for row in rows:
        classification = classify_place_record(row, rules)
        if not classification.is_indexable:
            excluded_reasons[classification.exclusion_reason or "분류 정책상 제외"] += 1
            continue
        content_id = first_value(row, "contentid")
        membership = grouping.memberships.get(content_id)
        if membership is not None and not membership.is_primary_place:
            excluded_reasons[
                f"대표 장소에 병합된 중복 장소 ({membership.relationship_type})"
            ] += 1
            continue
        documents.append(
            build_place_vector_document(
                row,
                classification,
                rules.preprocessing_version,
                group_membership=membership,
                related_places=relationship_index.get(content_id, ()),
                aliases=group_aliases.get(content_id, ()),
                merged_content_ids=merged_content_ids.get(content_id, ()),
            )
        )

    return PlacePreprocessResult(
        documents=documents,
        source_record_count=len(rows),
        excluded_count=sum(excluded_reasons.values()),
        excluded_by_reason=dict(sorted(excluded_reasons.items())),
        dataset_counts=dict(
            sorted(Counter(doc["metadata"]["dataset"] for doc in documents).items())
        ),
        collection_counts=dict(
            sorted(Counter(doc["metadata"]["target_collection"] for doc in documents).items())
        ),
        scope_counts=dict(
            sorted(Counter(doc["metadata"]["recommendation_scope"] for doc in documents).items())
        ),
        subtype_counts=dict(
            sorted(Counter(doc["metadata"]["place_subtype"] for doc in documents).items())
        ),
        itinerary_role_counts=dict(
            sorted(Counter(doc["metadata"]["itinerary_role"] for doc in documents).items())
        ),
        route_ineligible_count=sum(not doc["metadata"]["route_eligible"] for doc in documents),
        preprocessing_version=rules.preprocessing_version,
        place_groups=grouping.groups,
        place_relationships=active_relationships,
    )


def build_place_vector_document(
    record: Mapping[str, Any],
    classification: Classification,
    preprocessing_version: str,
    *,
    group_membership: PlaceGroupMember | None = None,
    related_places: Sequence[RelatedPlace] = (),
    aliases: Sequence[str] = (),
    merged_content_ids: Sequence[str] = (),
) -> dict[str, Any]:
    dataset = first_value(record, "dataset") or "tourism"
    content_id = first_value(record, "contentid", "contentId")
    content_type_id = first_value(record, "contenttypeid", "contentTypeId")
    title = clean_text(first_value(record, "common_title", "title"))
    overview = clean_text(first_value(record, "common_overview"))
    addr1 = clean_text(first_value(record, "common_addr1", "addr1"))
    addr2 = clean_text(first_value(record, "common_addr2", "addr2"))
    address = " ".join(part for part in (addr1, addr2) if part)
    city, district = parse_address(addr1)
    longitude, latitude = validated_coordinates(
        first_value(record, "common_mapx", "mapx"),
        first_value(record, "common_mapy", "mapy"),
    )
    lcls1 = first_value(record, "common_lclsSystm1", "lclsSystm1")
    lcls2 = first_value(record, "common_lclsSystm2", "lclsSystm2")
    lcls3 = first_value(record, "common_lclsSystm3", "lclsSystm3")
    tags = _tags(content_type_id, lcls1, classification.place_subtype)
    route_eligible = _route_eligible(classification, address, longitude, latitude)

    opening_hours = _clean_first(record, *OPENING_HOURS_FIELDS)
    closed_days = _clean_first(record, *CLOSED_DAYS_FIELDS)
    check_in_time = _clean_first(record, "intro_checkintime")
    check_out_time = _clean_first(record, "intro_checkouttime")
    hours_available = bool(opening_hours)
    lodging_times_available = classification.target_collection == "lodgings" and bool(
        check_in_time or check_out_time
    )

    feature_values = {
        "체험": _clean_first(record, "intro_expguide"),
        "대표 메뉴": _clean_first(record, "intro_firstmenu"),
        "취급 메뉴": _clean_first(record, "intro_treatmenu"),
        "판매 품목": _clean_first(record, "intro_saleitem"),
        "매장 안내": _clean_first(record, "intro_shopguide"),
        "레저 종목": _clean_first(record, "intro_sports"),
        "객실 유형": _clean_first(record, "intro_roomtype"),
        "부대시설": _clean_first(record, "intro_subfacility"),
    }
    place_group_id = group_membership.place_group_id if group_membership else ""
    canonical_content_id = (
        group_membership.canonical_content_id if group_membership else content_id
    )
    relationship_type = (
        group_membership.relationship_type if group_membership else "standalone"
    )
    is_primary_place = (
        group_membership.is_primary_place if group_membership else True
    )
    related_metadata = related_places_payload(related_places)
    parent_content_ids = [
        related.content_id
        for related in related_places
        if related.relation_role == "child"
    ]

    return {
        "id": f"tourapi:{content_id}",
        "embedding_text": _embedding_text(
            title, aliases, city, district, overview, tags, feature_values
        ),
        "metadata": {
            "contentid": content_id,
            "dataset": dataset,
            "title": title,
            "aliases": list(aliases),
            "merged_contentids": list(merged_content_ids),
            "entity_type": classification.entity_type,
            "place_subtype": classification.place_subtype,
            "itinerary_role": classification.itinerary_role,
            "target_collection": classification.target_collection,
            "recommendation_scope": classification.recommendation_scope,
            "requires_verification": classification.requires_verification,
            "route_eligible": route_eligible,
            "is_itinerary_stop": classification.is_itinerary_stop and is_primary_place,
            "place_group_id": place_group_id,
            "canonical_contentid": canonical_content_id,
            "relationship_type": relationship_type,
            "is_primary_place": is_primary_place,
            "parent_contentid": parent_content_ids[0] if len(parent_content_ids) == 1 else "",
            "related_contentids": [
                related.content_id for related in related_places
            ],
            "related_relationship_types": sorted(
                {related.relationship_type for related in related_places}
            ),
            "related_places": related_metadata,
            "content_type_id": content_type_id,
            "content_type_label": CONTENT_TYPE_LABELS.get(content_type_id, ""),
            "overview_available": bool(overview),
            "lcls1": lcls1,
            "lcls2": lcls2,
            "lcls3": lcls3,
            "tags": tags,
            "addr1": addr1,
            "addr2": addr2,
            "address": address,
            "city": city,
            "district": district,
            "latitude": latitude,
            "longitude": longitude,
            "coordinate_verified": longitude is not None and latitude is not None,
            "opening_hours_raw": opening_hours,
            "closed_days_raw": closed_days,
            "parking_raw": _clean_first(record, *PARKING_FIELDS),
            "info_center": _clean_first(record, *INFO_CENTER_FIELDS),
            "use_fee_raw": _clean_first(record, *USE_FEE_FIELDS),
            "spend_time_raw": _clean_first(record, "intro_spendtime"),
            "experience_age_raw": _clean_first(record, *EXPERIENCE_AGE_FIELDS),
            "experience_guide_raw": feature_values["체험"],
            "reservation_raw": _clean_first(record, *RESERVATION_FIELDS),
            "baby_carriage_raw": _clean_first(record, *BABY_CARRIAGE_FIELDS),
            "pet_allowed_raw": _clean_first(record, *PET_FIELDS),
            "credit_card_raw": _clean_first(record, *CREDIT_CARD_FIELDS),
            "check_in_time": check_in_time,
            "check_out_time": check_out_time,
            "first_menu_raw": feature_values["대표 메뉴"],
            "treat_menu_raw": feature_values["취급 메뉴"],
            "packing_raw": _clean_first(record, "intro_packing"),
            "kids_facility_raw": _clean_first(record, "intro_kidsfacility"),
            "sale_item_raw": feature_values["판매 품목"],
            "sale_item_cost_raw": _clean_first(record, "intro_saleitemcost"),
            "shop_guide_raw": feature_values["매장 안내"],
            "fair_day_raw": _clean_first(record, "intro_fairday"),
            "room_type_raw": feature_values["객실 유형"],
            "subfacility_raw": feature_values["부대시설"],
            "sports_raw": feature_values["레저 종목"],
            "use_season_raw": _clean_first(record, "intro_useseason", "intro_openperiod"),
            "hours_available": hours_available,
            "schedule_eligible": bool(
                route_eligible and (hours_available or lodging_times_available)
            ),
            "common_fetch_status": first_value(record, "common_fetch_status"),
            "intro_fetch_status": first_value(record, "intro_fetch_status"),
            "intro_fetched_at": first_value(record, "intro_fetched_at"),
            "homepage": extract_first_url(first_value(record, "common_homepage")),
            "image_url": first_value(record, "common_firstimage", "firstimage"),
            "source_modified_at": first_value(
                record, "common_modifiedtime", "modifiedtime"
            ),
            "source": "TourAPI",
            "preprocessing_version": preprocessing_version,
        },
    }


def build_place_vector_payload(
    result: PlacePreprocessResult,
    *,
    source_file: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "source": {
            "provider": "TourAPI",
            "file": source_file,
            "record_count": result.source_record_count,
        },
        "preprocessing_version": result.preprocessing_version,
        "statistics": {
            "document_count": len(result.documents),
            "excluded_count": result.excluded_count,
            "excluded_by_reason": result.excluded_by_reason,
            "dataset_counts": result.dataset_counts,
            "collection_counts": result.collection_counts,
            "recommendation_scope_counts": result.scope_counts,
            "place_subtype_counts": result.subtype_counts,
            "itinerary_role_counts": result.itinerary_role_counts,
            "route_ineligible_count": result.route_ineligible_count,
            "place_group_count": len(result.place_groups),
            "place_relationship_count": len(result.place_relationships),
            "grouped_source_record_count": sum(
                len(group.members) for group in result.place_groups
            ),
        },
        "place_groups": place_groups_payload(result.place_groups),
        "place_relationships": place_relationships_payload(
            result.place_relationships
        ),
        "documents": result.documents,
    }


def write_place_vector_payload(payload: Mapping[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temp_path.replace(path)


def _validate_source_rows(rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError("place CSV has no records")
    required_fields = {"dataset", "contentid", "contenttypeid", "title", "common_overview"}
    missing_fields = required_fields.difference(rows[0])
    if missing_fields:
        raise ValueError(f"place CSV is missing required fields: {sorted(missing_fields)}")

    content_ids = [first_value(row, "contentid") for row in rows]
    if any(not content_id for content_id in content_ids):
        raise ValueError("place CSV contains a blank contentid")
    duplicates = sorted(
        content_id for content_id, count in Counter(content_ids).items() if count > 1
    )
    if duplicates:
        raise ValueError(f"place CSV contains duplicate contentids: {duplicates[:10]}")
    for row in rows:
        content_id = first_value(row, "contentid")
        for field in ("dataset", "title"):
            if not first_value(row, field):
                raise ValueError(f"contentid={content_id} is missing required field {field}")


def _route_eligible(
    classification: Classification,
    address: str,
    longitude: float | None,
    latitude: float | None,
) -> bool:
    if classification.route_eligible_override is not None:
        return classification.route_eligible_override
    return bool(address and longitude is not None and latitude is not None)


def _tags(content_type_id: str, lcls1: str, place_subtype: str = "") -> list[str]:
    return [
        tag
        for tag in (
            CONTENT_TYPE_LABELS.get(content_type_id, ""),
            LCLS1_LABELS.get(lcls1, ""),
            PLACE_SUBTYPE_LABELS.get(place_subtype, ""),
        )
        if tag
    ]


def _clean_first(record: Mapping[str, Any], *fields: str) -> str:
    return clean_text(first_value(record, *fields))


def _embedding_text(
    title: str,
    aliases: Sequence[str],
    city: str,
    district: str,
    overview: str,
    tags: Sequence[str],
    features: Mapping[str, str],
) -> str:
    sections = [f"장소명: {title}"]
    if aliases:
        sections.append(f"다른 이름: {', '.join(aliases)}")
    if tags:
        sections.append(f"유형: {', '.join(tags)}")
    location = " ".join(part for part in (city, district) if part)
    if location:
        sections.append(f"지역: {location}")
    if overview:
        sections.append(f"설명: {overview}")
    sections.extend(f"{label}: {value}" for label, value in features.items() if value)
    return "\n".join(sections)
