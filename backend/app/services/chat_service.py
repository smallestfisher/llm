from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Run, Thread, Turn
from app.workflow.filters import extract_shared_filters
from app.workflow.history import build_history_from_messages
from app.workflow.router import decide_route


class ChatService:
    def build_route_snapshot(self, question: str) -> dict:
        decision = decide_route(question)
        return {
            "route": decision.route,
            "confidence": decision.confidence,
            "matched_domains": decision.matched_domains,
            "target_tables": decision.target_tables,
            "filters": decision.filters,
            "reason": decision.reason,
        }

    def attach_route_to_run(self, run: Run, question: str) -> dict:
        snapshot = self.build_route_snapshot(question)
        run.route = snapshot["route"]
        run.route_reason = snapshot["reason"]
        run.current_step = "route"
        return snapshot

    def build_thread_history(self, db: Session, thread: Thread) -> list[str]:
        turns = db.query(Turn).filter(Turn.thread_id == thread.id).order_by(Turn.sequence.asc()).all()
        messages: list[object] = []
        for turn in turns:
            if turn.user_message:
                messages.append(turn.user_message)
            if turn.latest_assistant_message:
                messages.append(turn.latest_assistant_message)
        return build_history_from_messages(messages)

    def shared_filters(self, question: str) -> dict:
        return extract_shared_filters(question)
