from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Protocol, Sequence

from .models import NormalizedItinerary, ScoredPackage


@dataclass(frozen=True)
class RankDecision:
    package_id: str
    reason: str


class PackageRanker(Protocol):
    def rank(
        self,
        itinerary: NormalizedItinerary,
        candidates: Sequence[ScoredPackage],
    ) -> list[RankDecision]: ...


class OpenAIPackageRanker:
    """Use an LLM only to resolve ties and write grounded explanations."""

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini") -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai is not installed; run: pip install -r requirements.txt") from exc
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def rank(
        self,
        itinerary: NormalizedItinerary,
        candidates: Sequence[ScoredPackage],
    ) -> list[RankDecision]:
        allowed_ids = {row.package.package_id for row in candidates}
        response = self._client.responses.create(
            model=self._model,
            instructions=(
                "You rank Jeju travel packages. Never invent places or facts. "
                "Exact content_id overlap has already been calculated by code. "
                "Use user-profile fit and route evidence only as tie breakers. "
                "Return every candidate exactly once. Write each reason in Korean."
            ),
            input=json.dumps(
                {
                    "conditions": itinerary.conditions,
                    "itinerary_places": [
                        {
                            "content_id": row.content_id,
                            "title": row.title,
                            "day": row.day,
                            "sequence": row.sequence,
                        }
                        for row in itinerary.tourism_stops
                    ],
                    "candidates": [_candidate_evidence(row) for row in candidates],
                },
                ensure_ascii=False,
            ),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "package_ranking",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "ranking": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "package_id": {"type": "string"},
                                        "reason": {"type": "string"},
                                    },
                                    "required": ["package_id", "reason"],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["ranking"],
                        "additionalProperties": False,
                    },
                }
            },
        )
        payload = json.loads(response.output_text)
        decisions = [
            RankDecision(str(row["package_id"]), str(row["reason"]))
            for row in payload["ranking"]
        ]
        returned_ids = [row.package_id for row in decisions]
        if len(returned_ids) != len(set(returned_ids)) or set(returned_ids) != allowed_ids:
            raise ValueError("LLM ranking contains missing, duplicate, or unknown package IDs")
        return decisions


def deterministic_reason(candidate: ScoredPackage) -> str:
    matched = candidate.exact_match_count
    total = candidate.itinerary_place_count
    if matched:
        names = [
            item.title
            for item in candidate.package.tourism_items
            if item.content_id in candidate.matched_content_ids
        ][:3]
        place_text = ", ".join(names) if names else "일정 관광지"
        return (
            f"일정 관광지 {total}곳 중 {matched}곳({place_text})이 정확히 겹치고, "
            f"동선·사용자 조건을 포함한 점수는 {candidate.score.total:.2f}점입니다."
        )
    return (
        "정확히 겹치는 관광지는 없지만 사용자 조건과 인접 관광지 근거를 "
        f"반영한 점수가 {candidate.score.total:.2f}점입니다."
    )


def _candidate_evidence(candidate: ScoredPackage) -> dict[str, Any]:
    return {
        "package_id": candidate.package.package_id,
        "title": candidate.package.title,
        "summary": candidate.package.summary,
        "region": candidate.package.region,
        "match_profile": candidate.package.match_profile,
        "exact_match_count": candidate.exact_match_count,
        "matched_content_ids": list(candidate.matched_content_ids),
        "score": {
            "exact_overlap": candidate.score.exact_overlap,
            "route_fit": candidate.score.route_fit,
            "profile_fit": candidate.score.profile_fit,
            "nearby_fit": candidate.score.nearby_fit,
            "total": candidate.score.total,
        },
    }
