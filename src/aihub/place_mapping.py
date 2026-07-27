"""Match canonical AIHub places to TourAPI places.

The public imports remain here for compatibility. Visit grouping and shared
place identity helpers live in :mod:`src.aihub.place_identity`.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from difflib import SequenceMatcher
import math
from typing import Iterable

from .place_identity import (
    _MATCH_BUCKET_DEGREES,
    _MATCH_RADIUS_METERS,
    _bucket,
    _name_bigrams,
    _name_variants,
    GroupedAIHubPlace,
    PlaceMappingResult,
    TourPlaceCandidate,
    VisitPlaceRecord,
    group_aihub_visits,
    haversine_meters,
    normalize_address,
    normalize_name,
    valid_jeju_coordinate,
)


class TourPlaceMatcher:
    def __init__(self, places: Iterable[TourPlaceCandidate]) -> None:
        self.places = tuple(places)
        self._by_content_id = {place.content_id: place for place in self.places}
        self._by_name: dict[str, list[TourPlaceCandidate]] = defaultdict(list)
        self._by_address: dict[str, list[TourPlaceCandidate]] = defaultdict(list)
        self._by_bucket: dict[tuple[int, int], list[TourPlaceCandidate]] = defaultdict(list)
        self._by_name_bigram: dict[str, dict[int, TourPlaceCandidate]] = defaultdict(dict)
        for place in self.places:
            for name in (place.title, *place.aliases):
                for normalized in _name_variants(name):
                    self._by_name[normalized].append(place)
                    for bigram in _name_bigrams(normalized):
                        self._by_name_bigram[bigram][place.content_id] = place
            address = normalize_address(place.address)
            if address:
                self._by_address[address].append(place)
            if valid_jeju_coordinate(place.longitude, place.latitude):
                self._by_bucket[
                    _bucket(place.longitude, place.latitude, _MATCH_BUCKET_DEGREES)
                ].append(place)

    def match(self, place: GroupedAIHubPlace) -> PlaceMappingResult:
        names: set[str] = set()
        for name in (place.canonical_name, *place.aliases):
            names.update(_name_variants(name))
        address = normalize_address(place.road_address) or normalize_address(place.lot_address)
        candidates: dict[int, TourPlaceCandidate] = {}
        for name in names:
            for candidate in self._by_name.get(name, ()):
                candidates[candidate.content_id] = candidate
            shared_bigrams: Counter[int] = Counter()
            bigrams = _name_bigrams(name)
            for bigram in bigrams:
                shared_bigrams.update(self._by_name_bigram.get(bigram, {}).keys())
            minimum_shared = 1 if len(bigrams) <= 2 else 2
            for content_id, shared_count in shared_bigrams.items():
                if shared_count >= minimum_shared:
                    candidates[content_id] = self._by_content_id[content_id]
        if address:
            for candidate in self._by_address.get(address, ()):
                candidates[candidate.content_id] = candidate
        if valid_jeju_coordinate(place.longitude, place.latitude):
            center_x, center_y = _bucket(
                place.longitude,
                place.latitude,
                _MATCH_BUCKET_DEGREES,
            )
            for offset_x in range(-2, 3):
                for offset_y in range(-2, 3):
                    for candidate in self._by_bucket.get(
                        (center_x + offset_x, center_y + offset_y), ()
                    ):
                        if not valid_jeju_coordinate(candidate.longitude, candidate.latitude):
                            continue
                        distance = haversine_meters(
                            place.longitude,
                            place.latitude,
                            candidate.longitude,
                            candidate.latitude,
                        )
                        if distance <= _MATCH_RADIUS_METERS:
                            candidates[candidate.content_id] = candidate

        ranked = [self._score(place, candidate) for candidate in candidates.values()]
        ranked.sort(
            key=lambda item: (
                -item[0],
                item[2] if item[2] is not None else math.inf,
            )
        )
        if not ranked:
            return self._unmatched(place)

        score, candidate, distance, similarity, exact_name, address_match = ranked[0]
        runner_score = ranked[1][0] if len(ranked) > 1 else 0.0
        margin = score - runner_score

        if exact_name and address_match:
            return self._result(
                place,
                candidate,
                "MATCHED",
                "EXACT_NAME_ADDRESS",
                similarity,
                distance,
                max(score, 0.99),
            )
        if exact_name and distance is not None and distance <= 150.0:
            return self._result(
                place,
                candidate,
                "MATCHED",
                "EXACT_NAME_COORD",
                similarity,
                distance,
                max(score, 0.97),
            )
        if address_match and similarity >= 0.82 and (distance is None or distance <= 1000.0):
            return self._result(
                place,
                candidate,
                "REVIEW",
                "FUZZY_NAME_REVIEW",
                similarity,
                distance,
                score,
            )
        if exact_name:
            return self._result(
                place,
                candidate,
                "REVIEW",
                "EXACT_NAME_REVIEW",
                similarity,
                distance,
                score,
            )
        if distance is not None and distance <= 250.0 and similarity >= 0.75 and margin >= 0.03:
            return self._result(
                place,
                candidate,
                "REVIEW",
                "FUZZY_NAME_REVIEW",
                similarity,
                distance,
                score,
            )
        return self._unmatched(place)

    @staticmethod
    def _score(
        place: GroupedAIHubPlace,
        candidate: TourPlaceCandidate,
    ) -> tuple[float, TourPlaceCandidate, float | None, float, bool, bool]:
        source_names = set().union(
            *(_name_variants(value) for value in (place.canonical_name, *place.aliases))
        )
        candidate_names = set().union(
            *(_name_variants(value) for value in (candidate.title, *candidate.aliases))
        )
        similarities = [
            SequenceMatcher(None, source, target).ratio()
            for source in source_names
            for target in candidate_names
            if source and target
        ]
        similarity = max(similarities, default=0.0)
        exact_name = any(
            source == target
            for source in source_names
            for target in candidate_names
            if source and target
        )
        source_address = normalize_address(
            place.road_address
        ) or normalize_address(place.lot_address)
        target_address = normalize_address(candidate.address)
        address_match = bool(
            source_address
            and target_address
            and source_address == target_address
        )

        distance = None
        source_coordinate_valid = valid_jeju_coordinate(
            place.longitude,
            place.latitude,
        )
        target_coordinate_valid = valid_jeju_coordinate(
            candidate.longitude,
            candidate.latitude,
        )
        if source_coordinate_valid and target_coordinate_valid:
            distance = haversine_meters(
                place.longitude,
                place.latitude,
                candidate.longitude,
                candidate.latitude,
            )
        distance_score = 0.0 if distance is None else max(0.0, 1.0 - distance / 500.0)
        score = similarity * 0.78 + distance_score * 0.22
        if address_match:
            score = min(1.0, score + 0.08)
        return score, candidate, distance, similarity, exact_name, address_match

    @staticmethod
    def _result(
        place: GroupedAIHubPlace,
        candidate: TourPlaceCandidate,
        status: str,
        method: str,
        similarity: float,
        distance: float | None,
        confidence: float,
    ) -> PlaceMappingResult:
        return PlaceMappingResult(
            aihub_place_id=place.aihub_place_id,
            tourapi_content_id=candidate.content_id,
            status=status,
            method=method,
            name_similarity=round(similarity, 4),
            distance_m=round(distance, 2) if distance is not None else None,
            confidence_score=round(min(confidence, 1.0), 4),
        )

    @staticmethod
    def _unmatched(place: GroupedAIHubPlace) -> PlaceMappingResult:
        return PlaceMappingResult(
            aihub_place_id=place.aihub_place_id,
            tourapi_content_id=None,
            status="UNMATCHED",
            method="NO_RELIABLE_CANDIDATE",
            name_similarity=None,
            distance_m=None,
            confidence_score=0.0,
        )
