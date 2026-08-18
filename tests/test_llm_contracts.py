from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from types import SimpleNamespace
import unittest

from src.llm.client import LLMClientError, OpenAIChatClient
from src.llm.service import LLMService
from src.models.travel_condition import (
    LocalTransport,
    PartyType,
    TravelCondition,
    VisitPreference,
)


class FakeJsonClient:
    def __init__(self, *responses) -> None:
        self.responses = list(responses)
        self.calls = []

    def complete_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _condition() -> TravelCondition:
    return TravelCondition(
        duration_days=1,
        party_type=PartyType.SOLO,
        local_transport=LocalTransport.PUBLIC_TRANSIT,
        preferred_visit_types=(VisitPreference.NATURE,),
        companion_count=1,
    )


def _chat_client(model: str, content: str) -> tuple[OpenAIChatClient, FakeCompletions]:
    completions = FakeCompletions(content)
    client = object.__new__(OpenAIChatClient)
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    client.model = model
    client.reasoning_effort = "low"
    client.temperature = 0.25
    return client, completions


class OpenAIChatClientTests(unittest.TestCase):
    def test_gpt_56_uses_reasoning_effort_and_json_mode(self) -> None:
        client, completions = _chat_client("gpt-5.6-luna", '{"ok": true}')
        result = client.complete_json(system_prompt="system", user_prompt="user")

        self.assertEqual(result, {"ok": True})
        request = completions.calls[0]
        self.assertEqual(request["reasoning_effort"], "low")
        self.assertNotIn("temperature", request)
        self.assertEqual(request["response_format"], {"type": "json_object"})

    def test_other_models_use_temperature(self) -> None:
        client, completions = _chat_client("gpt-4.1-mini", "{}")
        client.complete_json(system_prompt="system", user_prompt="user")
        self.assertEqual(completions.calls[0]["temperature"], 0.25)
        self.assertNotIn("reasoning_effort", completions.calls[0])

    def test_invalid_json_is_wrapped(self) -> None:
        client, _ = _chat_client("gpt-4.1-mini", "not-json")
        with self.assertRaisesRegex(LLMClientError, "valid JSON"):
            client.complete_json(system_prompt="system", user_prompt="user")


class LLMServiceTests(unittest.TestCase):
    def test_extracts_travel_condition(self) -> None:
        fake = FakeJsonClient(
            {
                "duration_days": 2,
                "party_type": "solo",
                "local_transport": "rental_car",
                "preferred_visit_types": ["nature"],
                "companion_count": 1,
            }
        )
        with redirect_stdout(StringIO()):
            condition = LLMService(fake).extract_travel_condition("제주 자연 여행")
        self.assertEqual(condition.duration_days, 2)
        self.assertEqual(condition.preferred_visit_types, (VisitPreference.NATURE,))

    def test_invalid_condition_payload_is_wrapped(self) -> None:
        fake = FakeJsonClient({"party_type": "invalid", "local_transport": "rental_car"})
        with redirect_stdout(StringIO()):
            with self.assertRaisesRegex(LLMClientError, "invalid payload"):
                LLMService(fake).extract_travel_condition("여행")

    def test_query_generators_reject_blank_query(self) -> None:
        service = LLMService(FakeJsonClient({"query": " "}, {"query": None}))
        with self.assertRaisesRegex(LLMClientError, "empty query"):
            service.generate_search_query(_condition(), slot_role="visit", day=1)
        with self.assertRaisesRegex(LLMClientError, "empty query"):
            service.generate_style_query(_condition())

    def test_itinerary_and_revision_require_days_key(self) -> None:
        service = LLMService(FakeJsonClient({}, {}))
        with self.assertRaisesRegex(LLMClientError, "missing 'days'"):
            service.generate_itinerary(_condition(), [])
        with redirect_stdout(StringIO()):
            with self.assertRaisesRegex(LLMClientError, "missing 'days'"):
                service.revise_itinerary(_condition(), {"days": []}, [])

    def test_generation_repairs_content_id_outside_candidates(self) -> None:
        response = {
            "days": [
                {"day": 1, "stops": [{"sequence": 1, "role": "visit", "content_id": 999}]}
            ]
        }
        candidates = [
            {
                "day": 1,
                "slots": [
                    {
                        "day": 1,
                        "sequence": 1,
                        "role": "visit",
                        "candidates": [{"content_id": 1, "title": "협재해변"}],
                    }
                ],
            }
        ]
        result = LLMService(FakeJsonClient(response)).generate_itinerary(
            _condition(), candidates
        )
        stop = result["days"][0]["stops"][0]
        self.assertEqual(stop["content_id"], 1)
        self.assertEqual(stop["title"], "협재해변")

    def test_generation_repairs_duplicate_content_ids(self) -> None:
        response = {
            "days": [
                {
                    "day": 1,
                    "stops": [
                        {"sequence": 1, "role": "visit", "content_id": 1},
                        {"sequence": 2, "role": "visit", "content_id": 1},
                    ],
                }
            ]
        }
        candidates = [
            {
                "day": 1,
                "slots": [
                    {"sequence": 1, "candidates": [{"content_id": 1}]},
                    {"sequence": 2, "candidates": [{"content_id": 1}, {"content_id": 2}]},
                ],
            }
        ]
        result = LLMService(FakeJsonClient(response)).generate_itinerary(
            _condition(), candidates
        )
        self.assertEqual(
            [stop["content_id"] for stop in result["days"][0]["stops"]],
            [1, 2],
        )

    def test_revision_rejects_changes_outside_changed_slots(self) -> None:
        existing = {
            "days": [
                {
                    "day": 1,
                    "stops": [
                        {"sequence": 1, "role": "visit", "content_id": 1, "title": "기존"},
                        {"sequence": 2, "role": "food", "content_id": 2, "title": "식당"},
                    ],
                }
            ]
        }
        changed_slots = [
            {
                "day": 1,
                "sequence": 2,
                "role": "food",
                "candidates": [
                    {"content_id": 3, "title": "새 식당", "place": {"overview": "설명"}}
                ],
            }
        ]
        invalid_revision = json.loads(json.dumps(existing, ensure_ascii=False))
        invalid_revision["days"][0]["stops"][0]["content_id"] = 999

        with redirect_stdout(StringIO()):
            with self.assertRaisesRegex(LLMClientError, "unchanged"):
                LLMService(FakeJsonClient(invalid_revision)).revise_itinerary(
                    _condition(), existing, changed_slots
                )


if __name__ == "__main__":
    unittest.main()
