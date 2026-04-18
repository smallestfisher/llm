from __future__ import annotations

import unittest
from unittest import mock

from app.services import chat_service as chat_service_module


class FollowupEfficiencyTestCase(unittest.TestCase):
    def test_history_window_disabled_keeps_full_history(self) -> None:
        service = chat_service_module.ChatService()
        history = [f"问: q{i}\n答: a{i}" for i in range(1, 6)]
        with mock.patch.object(chat_service_module, "CHAT_HISTORY_WINDOW_TURNS", 0):
            output = service.apply_history_window(history)
        self.assertEqual(output, history)

    def test_history_window_with_summary(self) -> None:
        service = chat_service_module.ChatService()
        history = [f"问: q{i}\n答: a{i}" for i in range(1, 7)]
        with mock.patch.object(chat_service_module, "CHAT_HISTORY_WINDOW_TURNS", 2), mock.patch.object(
            chat_service_module, "CHAT_HISTORY_SUMMARY_ENABLED", True
        ), mock.patch.object(chat_service_module, "CHAT_HISTORY_SUMMARY_MAX_ITEMS", 3):
            output = service.apply_history_window(history)
        self.assertEqual(len(output), 3)
        self.assertTrue(output[0].startswith("历史摘要"))
        self.assertEqual(output[-2:], history[-2:])


if __name__ == "__main__":
    unittest.main()
