import unittest
from types import SimpleNamespace

from app.workflow import history as history_module
from app.workflow.history import build_history_from_messages, build_regenerate_seed_history, build_regenerate_seed_history_for_message


class ChatHistoryTestCase(unittest.TestCase):
    def test_build_history_ignores_incomplete_turn(self):
        messages = [
            SimpleNamespace(role="user", content="问题1"),
            SimpleNamespace(role="assistant", content="回答1"),
            SimpleNamespace(role="user", content="问题2"),
        ]

        history = build_history_from_messages(messages)

        self.assertEqual(history, ["问: 问题1\n答: 回答1"])

    def test_build_regenerate_seed_history_returns_prior_complete_turns(self):
        messages = [
            SimpleNamespace(role="user", content="问题1"),
            SimpleNamespace(role="assistant", content="回答1"),
            SimpleNamespace(role="user", content="问题2"),
            SimpleNamespace(role="assistant", content="回答2"),
        ]
        thread = SimpleNamespace(id=1)

        original = history_module.list_thread_messages
        history_module.list_thread_messages = lambda session, current_thread: messages
        try:
            history, last_user, last_assistant = build_regenerate_seed_history(None, thread)
        finally:
            history_module.list_thread_messages = original

        self.assertEqual(history, ["问: 问题1\n答: 回答1"])
        self.assertEqual(last_user.content, "问题2")
        self.assertEqual(last_assistant.content, "回答2")

    def test_build_regenerate_seed_history_rejects_incomplete_last_turn(self):
        messages = [
            SimpleNamespace(role="user", content="问题1"),
            SimpleNamespace(role="assistant", content="回答1"),
            SimpleNamespace(role="user", content="问题2"),
        ]
        thread = SimpleNamespace(id=1)

        original = history_module.list_thread_messages
        history_module.list_thread_messages = lambda session, current_thread: messages
        try:
            history, last_user, last_assistant = build_regenerate_seed_history(None, thread)
        finally:
            history_module.list_thread_messages = original

        self.assertEqual(history, ["问: 问题1\n答: 回答1"])
        self.assertEqual(last_user.content, "问题2")
        self.assertIsNone(last_assistant)

    def test_build_regenerate_seed_history_for_message_targets_specific_reply(self):
        messages = [
            SimpleNamespace(id=1, role="user", content="问题1"),
            SimpleNamespace(id=2, role="assistant", content="回答1"),
            SimpleNamespace(id=3, role="user", content="问题2"),
            SimpleNamespace(id=4, role="assistant", content="回答2"),
            SimpleNamespace(id=5, role="user", content="问题3"),
            SimpleNamespace(id=6, role="assistant", content="回答3"),
        ]
        thread = SimpleNamespace(id=1)

        original = history_module.list_thread_messages
        history_module.list_thread_messages = lambda session, current_thread: messages
        try:
            history, last_user, last_assistant = build_regenerate_seed_history_for_message(None, thread, 4)
        finally:
            history_module.list_thread_messages = original

        self.assertEqual(history, ["问: 问题1\n答: 回答1"])
        self.assertEqual(last_user.content, "问题2")
        self.assertEqual(last_assistant.content, "回答2")


if __name__ == "__main__":
    unittest.main()
