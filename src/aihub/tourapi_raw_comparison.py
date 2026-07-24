"""Classify TourAPI raw places by their relationship to filtered AIHub places."""

from __future__ import annotations

from collections import defaultdict
import csv
from dataclasses import dataclass, field
from difflib import SequenceMatcher
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .place_mapping import (
    GroupedAIHubPlace,
    PlaceMappingResult,
    TourPlaceCandidate,
    TourPlaceMatcher,
    _name_variants,
    haversine_meters,
    normalize_address,
    normalize_name,
    valid_jeju_coordinate,
)
from .row_values import (
    json_strings as _json_strings,
    optional_float as _optional_float,
    required_int as _required_int,
    stringify_row as _stringify_row,
)
from src.common.values import optional_text as _optional_text


CLASSIFICATION_COLUMNS = (
    "aihub_classification",
    "aihub_unmatched_reason",
    "aihub_candidate_place_id",
    "aihub_candidate_place_name",
    "aihub_candidate_address",
    "aihub_candidate_longitude",
    "aihub_candidate_latitude",
    "aihub_candidate_visit_count",
    "aihub_match_method",
    "aihub_name_similarity",
    "aihub_distance_m",
    "aihub_confidence_score",
)

_MATCH_BUCKET_DEGREES = 0.003
_MATCH_RADIUS_METERS = 500.0
_STATUS_PRIORITY = {"MATCHED": 2, "REVIEW": 1}


@dataclass(frozen=True)
class RawTourPlace:
    content_id: int
    title: str
    address1: str | None
    address2: str | None
    longitude: float | None
    latitude: float | None
    raw_row: Mapping[str, str] = field(default_factory=dict)

    def as_match_candidate(self) -> TourPlaceCandidate:
        return TourPlaceCandidate(
            content_id=self.content_id,
            title=self.title,
            aliases=(),
            address=self.address1,
            longitude=self.longitude,
            latitude=self.latitude,
        )


@dataclass(frozen=True)
class AIHubCandidate:
    source_row: Mapping[str, str]
    place: GroupedAIHubPlace


@dataclass(frozen=True)
class CandidateEvidence:
    candidate: AIHubCandidate
    name_similarity: float
    distance_m: float | None
    exact_name: bool
    address_match: bool
    confidence_score: float


@dataclass(frozen=True)
class TourApiClassificationSummary:
    tourapi_rows: int
    aihub_rows: int
    matched_rows: int
    aihub_candidate_unmatched_rows: int
    not_in_aihub_rows: int


def load_tourapi_raw_places(
    path: str | Path,
) -> tuple[tuple[str, ...], list[RawTourPlace]]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"TourAPI raw CSV does not exist: {source}")
    with source.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = tuple(reader.fieldnames or ())
        required = {"contentid", "title", "addr1", "mapx", "mapy"}
        missing = required.difference(fieldnames)
        if missing:
            raise ValueError(
                "TourAPI raw CSV is missing required columns: "
                + ", ".join(sorted(missing))
            )
        places = [raw_tour_place_from_row(row) for row in reader]
    if not places:
        raise ValueError("TourAPI raw CSV contains no data rows")
    content_ids = [place.content_id for place in places]
    if len(content_ids) != len(set(content_ids)):
        raise ValueError("TourAPI raw CSV contains duplicate contentid values")
    return fieldnames, places


def raw_tour_place_from_row(row: Mapping[str, Any]) -> RawTourPlace:
    content_id = _required_int(row.get("contentid"), "contentid")
    title = _first(row, "common_title", "title") or str(content_id)
    return RawTourPlace(
        content_id=content_id,
        title=title,
        address1=_optional_text(_first(row, "common_addr1", "addr1")),
        address2=_optional_text(_first(row, "common_addr2", "addr2")),
        longitude=_optional_float(_first(row, "common_mapx", "mapx")),
        latitude=_optional_float(_first(row, "common_mapy", "mapy")),
        raw_row=_stringify_row(row),
    )


def classify_tourapi_against_aihub(
    tourapi_places: Sequence[RawTourPlace],
    aihub_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, str]], TourApiClassificationSummary]:
    """Return one classified result row per TourAPI raw place."""

    if not tourapi_places:
        raise ValueError("TourAPI candidate rows are empty")
    if not aihub_rows:
        raise ValueError("AIHub recommendation rows are empty")

    aihub_candidates = [
        _aihub_candidate(_stringify_row(row)) for row in aihub_rows
    ]
    matcher = TourPlaceMatcher(
        place.as_match_candidate() for place in tourapi_places
    )
    links_by_tourapi: dict[
        int, list[tuple[PlaceMappingResult, AIHubCandidate]]
    ] = defaultdict(list)
    selected_tourapi_by_aihub: dict[int, int] = {}
    for candidate in aihub_candidates:
        result = matcher.match(candidate.place)
        if result.tourapi_content_id is not None:
            links_by_tourapi[result.tourapi_content_id].append((result, candidate))
            selected_tourapi_by_aihub[
                candidate.place.aihub_place_id
            ] = result.tourapi_content_id

    index = _AIHubEvidenceIndex(aihub_candidates)
    classified: list[dict[str, str]] = []
    counts = {
        "MATCHED": 0,
        "AIHUB_CANDIDATE_UNMATCHED": 0,
        "NOT_IN_AIHUB": 0,
    }
    for tourapi_place in tourapi_places:
        row, classification = _classify_tourapi_place(
            tourapi_place,
            links_by_tourapi.get(tourapi_place.content_id, ()),
            index,
            selected_tourapi_by_aihub,
        )
        classified.append(row)
        counts[classification] += 1

    classified.sort(
        key=lambda row: (
            _classification_priority(row["aihub_classification"]),
            int(row["contentid"]),
        )
    )
    return classified, TourApiClassificationSummary(
        tourapi_rows=len(tourapi_places),
        aihub_rows=len(aihub_rows),
        matched_rows=counts["MATCHED"],
        aihub_candidate_unmatched_rows=counts["AIHUB_CANDIDATE_UNMATCHED"],
        not_in_aihub_rows=counts["NOT_IN_AIHUB"],
    )


class _AIHubEvidenceIndex:
    def __init__(self, candidates: Sequence[AIHubCandidate]) -> None:
        self.candidates = tuple(candidates)
        self.by_name: dict[str, set[int]] = defaultdict(set)
        self.by_address: dict[str, set[int]] = defaultdict(set)
        self.by_bucket: dict[tuple[int, int], set[int]] = defaultdict(set)
        for index, candidate in enumerate(self.candidates):
            for name in (
                candidate.place.canonical_name,
                *candidate.place.aliases,
            ):
                for variant in _name_variants(name):
                    self.by_name[variant].add(index)
            address = normalize_address(candidate.place.road_address) or normalize_address(
                candidate.place.lot_address
            )
            if address:
                self.by_address[address].add(index)
            if valid_jeju_coordinate(
                candidate.place.longitude,
                candidate.place.latitude,
            ):
                self.by_bucket[
                    _bucket(candidate.place.longitude, candidate.place.latitude)
                ].add(index)

    def evidence_for(self, tourapi_place: RawTourPlace) -> list[CandidateEvidence]:
        indexes: set[int] = set()
        for variant in _name_variants(tourapi_place.title):
            indexes.update(self.by_name.get(variant, ()))
        address = normalize_address(tourapi_place.address1)
        if address:
            indexes.update(self.by_address.get(address, ()))
        if valid_jeju_coordinate(tourapi_place.longitude, tourapi_place.latitude):
            center_x, center_y = _bucket(
                tourapi_place.longitude,
                tourapi_place.latitude,
            )
            for offset_x in range(-2, 3):
                for offset_y in range(-2, 3):
                    for index in self.by_bucket.get(
                        (center_x + offset_x, center_y + offset_y), ()
                    ):
                        candidate = self.candidates[index]
                        distance = haversine_meters(
                            tourapi_place.longitude,
                            tourapi_place.latitude,
                            candidate.place.longitude,
                            candidate.place.latitude,
                        )
                        if distance <= _MATCH_RADIUS_METERS:
                            indexes.add(index)
        return [
            _score_evidence(self.candidates[index], tourapi_place)
            for index in indexes
        ]


def _classify_tourapi_place(
    tourapi_place: RawTourPlace,
    links: Sequence[tuple[PlaceMappingResult, AIHubCandidate]],
    index: _AIHubEvidenceIndex,
    selected_tourapi_by_aihub: Mapping[int, int],
) -> tuple[dict[str, str], str]:
    matched_links = [link for link in links if link[0].status == "MATCHED"]
    if matched_links:
        result, candidate = max(matched_links, key=_link_key)
        return (
            _classification_row(
                tourapi_place,
                "MATCHED",
                "",
                candidate,
                result.method,
                result.name_similarity,
                result.distance_m,
                result.confidence_score,
            ),
            "MATCHED",
        )

    review_links = [link for link in links if link[0].status == "REVIEW"]
    if review_links:
        result, candidate = max(review_links, key=_link_key)
        return (
            _classification_row(
                tourapi_place,
                "AIHUB_CANDIDATE_UNMATCHED",
                _review_reason(result),
                candidate,
                result.method,
                result.name_similarity,
                result.distance_m,
                result.confidence_score,
            ),
            "AIHUB_CANDIDATE_UNMATCHED",
        )

    nearby_evidence = sorted(
        index.evidence_for(tourapi_place),
        key=lambda item: (
            -item.confidence_score,
            item.distance_m if item.distance_m is not None else math.inf,
            -item.candidate.place.visit_count,
        ),
    )
    if not nearby_evidence:
        return (
            _classification_row(
                tourapi_place,
                "NOT_IN_AIHUB",
                "NO_NAME_ADDRESS_OR_NEARBY_CANDIDATE",
                None,
                "",
                None,
                None,
                None,
            ),
            "NOT_IN_AIHUB",
        )

    identity_evidence = [
        item for item in nearby_evidence if _has_identity_evidence(item)
    ]
    if not identity_evidence:
        return (
            _classification_row(
                tourapi_place,
                "NOT_IN_AIHUB",
                "NEARBY_PLACE_ONLY_NAME_MISMATCH",
                None,
                "",
                None,
                None,
                None,
            ),
            "NOT_IN_AIHUB",
        )

    best = identity_evidence[0]
    runner_score = (
        identity_evidence[1].confidence_score
        if len(identity_evidence) > 1
        else 0.0
    )
    selected_other = selected_tourapi_by_aihub.get(
        best.candidate.place.aihub_place_id
    )
    reason = _evidence_reason(
        best,
        runner_score=runner_score,
        selected_other_tourapi=(
            selected_other is not None and selected_other != tourapi_place.content_id
        ),
    )
    return (
        _classification_row(
            tourapi_place,
            "AIHUB_CANDIDATE_UNMATCHED",
            reason,
            best.candidate,
            "REVERSE_CANDIDATE",
            round(best.name_similarity, 4),
            round(best.distance_m, 2) if best.distance_m is not None else None,
            round(best.confidence_score, 4),
        ),
        "AIHUB_CANDIDATE_UNMATCHED",
    )


def _has_identity_evidence(evidence: CandidateEvidence) -> bool:
    """Exclude unrelated businesses that merely happen to be nearby."""

    if evidence.exact_name or evidence.address_match:
        return True
    return bool(
        evidence.distance_m is not None
        and evidence.distance_m <= 250.0
        and evidence.name_similarity >= 0.75
    )


def _score_evidence(
    candidate: AIHubCandidate,
    tourapi_place: RawTourPlace,
) -> CandidateEvidence:
    source_names = set().union(
        *(
            _name_variants(name)
            for name in (
                candidate.place.canonical_name,
                *candidate.place.aliases,
            )
        )
    )
    target_names = _name_variants(tourapi_place.title)
    similarity = max(
        (
            SequenceMatcher(None, source, target).ratio()
            for source in source_names
            for target in target_names
            if source and target
        ),
        default=0.0,
    )
    exact_name = bool(source_names.intersection(target_names))
    source_address = normalize_address(candidate.place.road_address) or normalize_address(
        candidate.place.lot_address
    )
    target_address = normalize_address(tourapi_place.address1)
    address_match = bool(
        source_address and target_address and source_address == target_address
    )
    distance = None
    if valid_jeju_coordinate(
        candidate.place.longitude,
        candidate.place.latitude,
    ) and valid_jeju_coordinate(tourapi_place.longitude, tourapi_place.latitude):
        distance = haversine_meters(
            candidate.place.longitude,
            candidate.place.latitude,
            tourapi_place.longitude,
            tourapi_place.latitude,
        )
    distance_score = 0.0 if distance is None else max(0.0, 1.0 - distance / 500.0)
    confidence = similarity * 0.78 + distance_score * 0.22
    if address_match:
        confidence = min(1.0, confidence + 0.08)
    return CandidateEvidence(
        candidate=candidate,
        name_similarity=similarity,
        distance_m=distance,
        exact_name=exact_name,
        address_match=address_match,
        confidence_score=confidence,
    )


def _review_reason(result: PlaceMappingResult) -> str:
    if result.method == "EXACT_NAME_REVIEW":
        if result.distance_m is None:
            return "EXACT_NAME_LOCATION_MISSING"
        return "EXACT_NAME_DISTANCE_OVER_150M"
    return "FUZZY_NAME_REQUIRES_REVIEW"


def _evidence_reason(
    evidence: CandidateEvidence,
    *,
    runner_score: float,
    selected_other_tourapi: bool,
) -> str:
    if evidence.address_match:
        return "SAME_ADDRESS_NAME_MISMATCH"
    if selected_other_tourapi:
        return "LOWER_RANKED_DUPLICATE_TOURAPI_CANDIDATE"
    if evidence.exact_name:
        return "EXACT_NAME_LOCATION_CONFLICT"
    if (
        evidence.distance_m is not None
        and evidence.distance_m <= 250.0
        and evidence.name_similarity >= 0.75
        and evidence.confidence_score - runner_score < 0.03
    ):
        return "AMBIGUOUS_NEARBY_CANDIDATES"
    if evidence.distance_m is not None and evidence.name_similarity < 0.75:
        return "NEARBY_LOW_NAME_SIMILARITY"
    return "CANDIDATE_BELOW_MATCH_THRESHOLD"


def _classification_row(
    tourapi_place: RawTourPlace,
    classification: str,
    reason: str,
    candidate: AIHubCandidate | None,
    method: str,
    name_similarity: float | None,
    distance_m: float | None,
    confidence_score: float | None,
) -> dict[str, str]:
    row = dict(tourapi_place.raw_row)
    row.update(
        {
            "aihub_classification": classification,
            "aihub_unmatched_reason": reason,
            "aihub_candidate_place_id": (
                str(candidate.place.aihub_place_id) if candidate else ""
            ),
            "aihub_candidate_place_name": (
                candidate.place.canonical_name if candidate else ""
            ),
            "aihub_candidate_address": (
                candidate.place.road_address
                or candidate.place.lot_address
                or ""
                if candidate
                else ""
            ),
            "aihub_candidate_longitude": _csv_value(
                candidate.place.longitude if candidate else None
            ),
            "aihub_candidate_latitude": _csv_value(
                candidate.place.latitude if candidate else None
            ),
            "aihub_candidate_visit_count": (
                str(candidate.place.visit_count) if candidate else ""
            ),
            "aihub_match_method": method,
            "aihub_name_similarity": _csv_value(name_similarity),
            "aihub_distance_m": _csv_value(distance_m),
            "aihub_confidence_score": _csv_value(confidence_score),
        }
    )
    return row


def _aihub_candidate(row: Mapping[str, str]) -> AIHubCandidate:
    place_id = _required_int(row.get("aihub_place_id"), "aihub_place_id")
    name = str(row.get("aihub_place_name") or "").strip()
    if not name:
        raise ValueError(f"AIHub place {place_id} has a blank name")
    return AIHubCandidate(
        source_row=row,
        place=GroupedAIHubPlace(
            aihub_place_id=place_id,
            canonical_name=name,
            normalized_name=str(
                row.get("aihub_normalized_name") or normalize_name(name)
            ),
            aliases=_json_strings(row.get("aihub_aliases")),
            poi_ids=_json_strings(row.get("aihub_poi_ids")),
            road_address=_optional_text(row.get("aihub_road_address")),
            lot_address=_optional_text(row.get("aihub_lot_address")),
            longitude=_optional_float(row.get("aihub_longitude")),
            latitude=_optional_float(row.get("aihub_latitude")),
            visit_area_type_cd=str(row.get("aihub_visit_area_type_code") or ""),
            visit_count=_required_int(
                row.get("aihub_visit_count"), "aihub_visit_count"
            ),
            identity_method=str(row.get("aihub_identity_method") or ""),
            member_keys=(("csv", str(place_id)),),
        ),
    )


def _link_key(
    link: tuple[PlaceMappingResult, AIHubCandidate],
) -> tuple[int, float, int, float]:
    result, candidate = link
    return (
        _STATUS_PRIORITY.get(result.status, 0),
        result.confidence_score,
        candidate.place.visit_count,
        -(result.distance_m if result.distance_m is not None else math.inf),
    )


def _classification_priority(value: str) -> int:
    return {
        "MATCHED": 1,
        "AIHUB_CANDIDATE_UNMATCHED": 2,
        "NOT_IN_AIHUB": 3,
    }.get(value, 4)


def _bucket(longitude: float, latitude: float) -> tuple[int, int]:
    return (
        math.floor(longitude / _MATCH_BUCKET_DEGREES),
        math.floor(latitude / _MATCH_BUCKET_DEGREES),
    )


def _first(row: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = str(row.get(name) or "").strip()
        if value:
            return value
    return ""


def _csv_value(value: Any) -> str:
    return "" if value is None else str(value)
