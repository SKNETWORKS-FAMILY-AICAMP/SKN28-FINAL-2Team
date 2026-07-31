from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.rag.llm import LLMError, OpenAITravelLLM
from src.rag.models import RetrievedPlace, SlotCandidates, SlotRequest, TravelConditions
from src.rag.orchestrator import build_itinerary_prompt_context


class _Responses:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        output = self.outputs.pop(0) if self.outputs else ""
        return SimpleNamespace(
            output_text=output,
            status="completed" if output else "incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=20,
                total_tokens=120,
            ),
        )


def _client(outputs: list[str]):
    return SimpleNamespace(responses=_Responses(outputs))


def test_condition_call_uses_bounded_history_and_output_budget(monkeypatch) -> None:
    monkeypatch.delenv("RAG_LLM_EMPTY_RESPONSE_RETRIES", raising=False)
    client = _client(
        [
            json.dumps(
                {
                    "duration_days": 2,
                    "party_type": "non_family_two",
                    "local_transport": "mixed",
                    "preferred_visit_types": ["nature"],
                }
            )
        ]
    )
    llm = OpenAITravelLLM(client=client)
    history = [
        {"role": "user", "content": f"{index}-" + "x" * 3000}
        for index in range(8)
    ]

    llm.extract_conditions(message="2일 여행", history=history)

    assert len(client.responses.calls) == 1
    call = client.responses.calls[0]
    assert call["max_output_tokens"] == 1800
    payload = json.loads(call["input"][1]["content"])
    assert len(payload["recent_history"]) == 4
    assert all(
        len(item["content"]) <= 1200
        for item in payload["recent_history"]
    )


def test_empty_output_does_not_resend_large_prompt_by_default(monkeypatch) -> None:
    monkeypatch.delenv("RAG_LLM_EMPTY_RESPONSE_RETRIES", raising=False)
    client = _client(["", "{}"])
    llm = OpenAITravelLLM(client=client)

    with pytest.raises(LLMError, match="after 1 attempt"):
        llm.extract_conditions(message="2일 여행")

    assert len(client.responses.calls) == 1


def test_itinerary_prompt_sends_only_selection_critical_fields(
    monkeypatch,
) -> None:
    monkeypatch.delenv("RAG_PROMPT_CANDIDATES_PER_SLOT", raising=False)
    conditions = TravelConditions.from_mapping(
        {
            "duration_days": 1,
            "party_type": "solo",
            "local_transport": "mixed",
            "preferred_visit_types": ["nature"],
        }
    )
    slot = SlotRequest(
        day=1,
        sequence=1,
        role="visit",
        category="nature",
        target_collections=("attractions",),
        itinerary_roles=("visit",),
        stay_minutes=None,
        latitude=None,
        longitude=None,
        radius_km=None,
    )
    places = tuple(
        RetrievedPlace(
            content_id=index,
            title=f"장소 {index}",
            latitude=33.4,
            longitude=126.5,
            similarity_score=0.9,
            rank=index,
            target_collection="attractions",
            itinerary_role="visit",
            tags=tuple(f"tag-{tag}" for tag in range(20)),
            overview="설명" * 1000,
            score_breakdown={"semantic": 0.8, "distance": 0.9},
        )
        for index in range(1, 6)
    )
    route_context = {
        "reference_trip_patterns": [
            {
                "reference_trip_id": "trip-1",
                "match_score": 90,
                "component_scores": {"duration": 100},
                "days": [
                    {
                        "day": 1,
                        "historical_average_satisfaction": 4.9,
                        "ignored_historical_anchors": {"lodging": 2},
                        "slots": [
                            {
                                "sequence": 1,
                                "role": "visit",
                                "category": "nature",
                                "target_collections": ["attractions"],
                                "itinerary_roles": ["visit"],
                                "stay_minutes": 60,
                            }
                        ],
                    }
                ],
            }
        ]
    }

    context = build_itinerary_prompt_context(
        conditions,
        route_context,
        [SlotCandidates(slot, "query", places)],
        frontend_selections={"duration_days": 1, "preferred_visit_types": ["nature"]},
    )

    candidates = context["slots"][0]["tourapi_candidates"]
    assert len(candidates) == 3
    assert all(
        set(candidate)
        == {
            "content_id",
            "title",
            "itinerary_role",
            "opening_hours",
            "closed_days",
            "parking",
            "rating",
            "distance_km",
            "operating_information_known",
        }
        for candidate in candidates
    )
    assert "overview" not in candidates[0]
    assert "tags" not in candidates[0]
    assert "address" not in candidates[0]
    assert "latitude" not in candidates[0]
    assert "longitude" not in candidates[0]
    assert "frontend_selections" not in context
    assert context["explicit_frontend_fields"] == [
        "duration_days",
        "preferred_visit_types",
    ]
    assert "aihub_reference_pattern" not in context
    assert "template_source" not in context["slots"][0]
    assert "route_anchor" not in context["slots"][0]
    assert "location_hint" not in context["slots"][0]
    assert len(
        json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    ) < 5_000
