from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Thread, Turn
from app.workflow.history import build_history_from_messages


class ChatService:
    def build_thread_history(self, db: Session, thread: Thread) -> list[str]:
        turns = db.query(Turn).filter(Turn.thread_id == thread.id).order_by(Turn.sequence.asc()).all()
        messages: list[object] = []
        for turn in turns:
            if turn.user_message:
                messages.append(turn.user_message)
            if turn.latest_assistant_message:
                messages.append(turn.latest_assistant_message)
        return build_history_from_messages(messages)
