from __future__ import annotations

import os

from sqlalchemy.orm import Session

from app.models import Thread, Turn
from app.workflow.history import build_history_from_messages


CHAT_HISTORY_WINDOW_TURNS = max(0, int(os.getenv("CHAT_HISTORY_WINDOW_TURNS", "0")))
CHAT_HISTORY_SUMMARY_ENABLED = os.getenv("CHAT_HISTORY_SUMMARY_ENABLED", "0") == "1"
CHAT_HISTORY_SUMMARY_MAX_ITEMS = max(1, int(os.getenv("CHAT_HISTORY_SUMMARY_MAX_ITEMS", "6")))
CHAT_HISTORY_SUMMARY_ITEM_MAX_CHARS = max(40, int(os.getenv("CHAT_HISTORY_SUMMARY_ITEM_MAX_CHARS", "140")))


class ChatService:
    def build_thread_history(self, db: Session, thread: Thread) -> list[str]:
        turns = db.query(Turn).filter(Turn.thread_id == thread.id).order_by(Turn.sequence.asc()).all()
        messages: list[object] = []
        for turn in turns:
            if turn.user_message:
                messages.append(turn.user_message)
            if turn.latest_assistant_message:
                messages.append(turn.latest_assistant_message)
        return self.apply_history_window(build_history_from_messages(messages))

    def apply_history_window(self, history: list[str]) -> list[str]:
        if CHAT_HISTORY_WINDOW_TURNS <= 0 or len(history) <= CHAT_HISTORY_WINDOW_TURNS:
            return history
        recent = history[-CHAT_HISTORY_WINDOW_TURNS:]
        if not CHAT_HISTORY_SUMMARY_ENABLED:
            return recent
        summary = self._build_history_summary(history[:-CHAT_HISTORY_WINDOW_TURNS])
        if not summary:
            return recent
        return [summary, *recent]

    def _build_history_summary(self, older_history: list[str]) -> str:
        if not older_history:
            return ""
        rows = older_history[-CHAT_HISTORY_SUMMARY_MAX_ITEMS:]
        lines = ["历史摘要（较早对话）:"]
        for index, row in enumerate(rows, start=1):
            question, answer = self._extract_pair(row)
            lines.append(f"{index}. 问: {self._clip_text(question)}")
            lines.append(f"   答: {self._clip_text(answer)}")
        return "\n".join(lines)

    @staticmethod
    def _extract_pair(history_row: str) -> tuple[str, str]:
        text = str(history_row or "")
        if "\n答:" not in text:
            return text, ""
        question_part, answer_part = text.split("\n答:", 1)
        question = question_part.removeprefix("问:").strip()
        answer = answer_part.strip()
        return question, answer

    @staticmethod
    def _clip_text(text: str) -> str:
        source = " ".join(str(text or "").split())
        if len(source) <= CHAT_HISTORY_SUMMARY_ITEM_MAX_CHARS:
            return source
        return source[: CHAT_HISTORY_SUMMARY_ITEM_MAX_CHARS - 3].rstrip() + "..."
