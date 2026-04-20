from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.conversation_resolver import ConversationResolver


class ConversationResolverTestCase(unittest.TestCase):
    def test_non_business_utterance_does_not_inherit_previous_query_context(self) -> None:
        resolver = ConversationResolver()
        previous_state = {
            "state_version": 1,
            "domain": "production",
            "domains": ["production"],
            "metric": "产量",
            "intent": "production_query",
            "query_text": "查询A1产线昨天产量",
            "dimensions": [],
            "filters": {"factory": "A1"},
            "presentation": {},
        }

        resolver.extract_latest_query_state = lambda messages: previous_state  # type: ignore[method-assign]

        with patch(
            "app.services.conversation_resolver.llm_complete",
            return_value="""
            {
              "mode": "ambiguous",
              "confidence": 0.5,
              "reason": "input is ambiguous and requires clarification",
              "query_op": {"type": "patch_state", "summary": "ambiguous follow-up"},
              "query_state": {"query_text": "你好", "filters": {}}
            }
            """,
        ):
            result = resolver.resolve(question="你好", messages=[])

        self.assertEqual(result["mode"], "ambiguous")
        self.assertEqual(result["query_op"]["type"], "new_query")
        self.assertEqual(result["query_state"]["domain"], "")
        self.assertEqual(result["query_state"]["domains"], [])
        self.assertEqual(result["query_state"]["filters"], {})
        self.assertEqual(result["query_state"]["query_text"], "你好")

    def test_normalize_query_state_for_new_query_does_not_merge_previous_filters(self) -> None:
        resolver = ConversationResolver()
        previous_state = {
            "state_version": 1,
            "domain": "production",
            "domains": ["production"],
            "metric": "产量",
            "intent": "production_query",
            "query_text": "查询A1产线昨天产量",
            "dimensions": [],
            "filters": {"factory": "A1"},
            "presentation": {},
        }

        normalized = resolver._normalize_query_state(
            {"query_text": "你好", "filters": {}},
            raw_question="你好",
            previous_state=previous_state,
        )

        self.assertEqual(normalized["filters"], {})
        self.assertEqual(normalized["domain"], "")
        self.assertEqual(normalized["query_text"], "你好")

    def test_standalone_query_text_keeps_raw_question_without_semantic_rewrite(self) -> None:
        resolver = ConversationResolver()
        raw_question = "最新四版需求，202604月P版需求最大的FGCODE是哪个"

        with patch(
            "app.services.conversation_resolver.llm_complete",
            return_value="""
            {
              "mode": "standalone_query",
              "confidence": 0.92,
              "reason": "standalone demand query",
              "query_op": {"type": "new_query", "summary": "new query"},
              "query_state": {
                "domain": "demand",
                "query_text": "查询2026年4月P版需求的最新四版，并找出需求量最大的FGCODE",
                "filters": {}
              }
            }
            """,
        ):
            result = resolver.resolve(question=raw_question, messages=[])

        self.assertEqual(result["mode"], "standalone_query")
        self.assertEqual(result["query_op"]["type"], "new_query")
        self.assertEqual(result["query_state"]["query_text"], raw_question)
        self.assertEqual(result["resolved_question"], raw_question)


if __name__ == "__main__":
    unittest.main()
