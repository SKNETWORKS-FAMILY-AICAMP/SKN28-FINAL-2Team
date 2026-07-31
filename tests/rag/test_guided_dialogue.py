from __future__ import annotations

import unittest

from src.rag.guided_dialogue import (
    start_guided_dialogue,
    submit_guided_answer,
)


class GuidedDialogueTests(unittest.TestCase):
    def test_collects_four_answers_in_required_order(self) -> None:
        state = start_guided_dialogue()

        self.assertEqual(state["field"], "duration_days")
        state = submit_guided_answer(state, "3일")
        self.assertEqual(state["field"], "party_size")
        state = submit_guided_answer(state, "2명")
        self.assertEqual(state["field"], "local_transport")
        state = submit_guided_answer(state, "렌터카")
        self.assertEqual(state["field"], "travel_style")
        state = submit_guided_answer(state, "힐링·여유")

        self.assertTrue(state["ready"])
        self.assertEqual(state["status"], "ready_to_generate")
        self.assertEqual(
            state["generation_inputs"],
            {
                "duration_days": 3,
                "party_size": 2,
                "local_transport": "rental_car",
                "travel_style": "healing",
            },
        )

    def test_invalid_answer_keeps_current_question(self) -> None:
        state = start_guided_dialogue()

        invalid = submit_guided_answer(state, "잘 모르겠어요")

        self.assertFalse(invalid["ready"])
        self.assertEqual(invalid["step_index"], 0)
        self.assertEqual(invalid["field"], "duration_days")
        self.assertIn("숫자", invalid["error"])

    def test_accepts_canonical_button_values(self) -> None:
        state = start_guided_dialogue()
        for answer in ("2", "4", "public_transit", "culture"):
            state = submit_guided_answer(state, answer)

        self.assertTrue(state["ready"])
        self.assertEqual(
            state["generation_inputs"]["local_transport"],
            "public_transit",
        )
        self.assertEqual(
            state["generation_inputs"]["travel_style"],
            "culture",
        )


if __name__ == "__main__":
    unittest.main()
