import unittest
from unittest import mock

from app.workflow.disambiguation import resolve_clarification_reply, resolve_disambiguation


class DisambiguationTestCase(unittest.TestCase):
    def test_disambiguation_clarifies_ambiguous_demand_query(self):
        with mock.patch("app.workflow.disambiguation.llm_complete", return_value='{"status":"clarify","question":"请确认是V版还是P版","reason":"ambiguous"}'):
            decision = resolve_disambiguation(
                question="本周预计需求",
                route="demand",
                structured_filters={"relative_week": "current_week"},
                allowed_tables=["p_demand", "v_demand", "product_attributes", "product_mapping"],
            )

        self.assertEqual(decision.status, "clarify")
        self.assertEqual(decision.clarification_type, "table_choice")
        self.assertIn("candidate_options", decision.clarification_context)

    def test_disambiguation_resolves_to_v_demand(self):
        with mock.patch("app.workflow.disambiguation.llm_complete", return_value='{"status":"resolved","chosen_option":"v_demand","reason":"forecast semantics"}'):
            decision = resolve_disambiguation(
                question="本周预计需求",
                route="demand",
                structured_filters={"relative_week": "current_week"},
                allowed_tables=["p_demand", "v_demand", "product_attributes", "product_mapping"],
            )

        self.assertEqual(decision.status, "resolved")
        self.assertEqual(decision.updated_filters.get("table"), "v_demand")
        self.assertEqual(decision.updated_filters.get("pm_version_table_type"), "V")

    def test_resolve_clarification_reply_rewrites_with_original_question(self):
        rewritten = resolve_clarification_reply(
            {
                "needs_clarification": True,
                "clarification_type": "table_choice",
                "clarification_context": {
                    "original_question": "本周预计需求",
                    "candidate_options": [
                        {"id": "v_demand", "label": "V版 forecast"},
                        {"id": "p_demand", "label": "P版承诺需求"},
                    ],
                },
            },
            "V版",
        )

        self.assertIn("本周预计需求", rewritten)
        self.assertIn("V版 forecast", rewritten)


if __name__ == "__main__":
    unittest.main()
