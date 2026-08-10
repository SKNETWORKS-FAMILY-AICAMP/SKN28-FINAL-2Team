import unittest
from types import SimpleNamespace

from src.llm.client import OpenAIChatClient


class FakeCompletions:
    def __init__(self) -> None:
        self.request = None

    def create(self, **request):
        self.request = request
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"ok": true}')
                )
            ]
        )


def make_fake_client():
    completions = FakeCompletions()
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )
    return client, completions


class OpenAIChatClientTests(unittest.TestCase):
    def test_complete_json_omits_temperature_by_default(self):
        client, completions = make_fake_client()
        llm = OpenAIChatClient(
            api_key="test-key",
            model="gpt-5-mini",
            client=client,
        )

        result = llm.complete_json(system_prompt="system", user_prompt="user")

        self.assertEqual(result, {"ok": True})
        self.assertNotIn("temperature", completions.request)

    def test_complete_json_includes_explicit_temperature(self):
        client, completions = make_fake_client()
        llm = OpenAIChatClient(
            api_key="test-key",
            model="gpt-4o-mini",
            temperature=0.2,
            client=client,
        )

        llm.complete_json(system_prompt="system", user_prompt="user")

        self.assertEqual(completions.request["temperature"], 0.2)


if __name__ == "__main__":
    unittest.main()
