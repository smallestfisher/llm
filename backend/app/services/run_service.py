from __future__ import annotations

import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Message, Run, Thread, Turn, utcnow
from app.repositories.thread_repository import ThreadRepository

ACTIVE_RUN_STATUSES = {'pending', 'running', 'cancelling'}
TERMINAL_RUN_STATUSES = {'completed', 'failed', 'cancelled'}


class RunService:
    def __init__(self) -> None:
        self.repo = ThreadRepository()

    def _next_turn_sequence(self, db: Session, thread_id: int) -> int:
        current = db.query(func.max(Turn.sequence)).filter(Turn.thread_id == thread_id).scalar()
        return int(current or 0) + 1

    def start_initial_run(self, db: Session, thread: Thread, question: str) -> tuple[Turn, Message, Run]:
        sequence = self._next_turn_sequence(db, thread.id)
        user_message = self.repo.create_message(db, thread_id=thread.id, turn_id=None, role='user', content=question)
        turn = self.repo.create_turn(db, thread_id=thread.id, sequence=sequence, user_message_id=user_message.id)
        user_message.turn_id = turn.id
        run = self.repo.create_run(db, thread_id=thread.id, turn_id=turn.id, kind='initial')
        run.status = 'pending'
        run.current_step = 'route'
        if thread.title == '新对话':
            thread.title = question.strip().replace('\n', ' ')[:48] or '新对话'
        thread.updated_at = utcnow()
        db.flush()
        return turn, user_message, run

    def update_message_metadata(self, db: Session, message: Message | None, metadata: dict | None = None) -> None:
        if not message:
            return
        message.metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        db.flush()

    def start_regenerate_run(self, db: Session, thread: Thread, assistant_message_id: int) -> tuple[Turn, Run] | None:
        messages = self.repo.list_messages_for_thread(db, thread.id)
        target = next((m for m in messages if m.id == assistant_message_id and m.role == 'assistant'), None)
        if not target or not target.turn_id:
            return None
        turn = db.query(Turn).filter(Turn.id == target.turn_id, Turn.thread_id == thread.id).first()
        if not turn:
            return None
        run = self.repo.create_run(db, thread_id=thread.id, turn_id=turn.id, kind='regenerate')
        run.status = 'pending'
        run.current_step = 'route'
        turn.status = 'pending'
        thread.updated_at = utcnow()
        db.flush()
        return turn, run

    def mark_run_running(self, db: Session, run: Run, *, current_step: str | None = None) -> None:
        run.status = 'running'
        if current_step is not None:
            run.current_step = current_step
        db.flush()

    def update_run_progress(
        self,
        db: Session,
        run: Run,
        *,
        current_step: str | None = None,
        route: str | None = None,
        route_reason: str | None = None,
        sql_query: str | None = None,
        error_message: str | None = None,
    ) -> None:
        if current_step is not None:
            run.current_step = current_step
        if route is not None:
            run.route = route
        if route_reason is not None:
            run.route_reason = route_reason
        if sql_query is not None:
            run.sql_query = sql_query
        if error_message is not None:
            run.error_message = error_message
        db.flush()

    def _replace_latest_assistant_message(self, db: Session, turn: Turn, new_message: Message) -> None:
        previous_message_id = turn.latest_assistant_message_id
        turn.latest_assistant_message_id = new_message.id
        if previous_message_id and previous_message_id != new_message.id:
            previous = db.query(Message).filter(Message.id == previous_message_id, Message.turn_id == turn.id).first()
            if previous:
                db.delete(previous)

    def complete_run(self, db: Session, run: Run, turn: Turn, answer: str, metadata: dict | None = None) -> Message:
        assistant = self.repo.create_message(
            db,
            thread_id=run.thread_id,
            turn_id=turn.id,
            role='assistant',
            content=answer,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
        self._replace_latest_assistant_message(db, turn, assistant)
        turn.status = 'completed'
        turn.updated_at = utcnow()
        run.status = 'completed'
        run.finished_at = utcnow()
        db.flush()
        return assistant

    def request_cancel(self, db: Session, run: Run, turn: Turn) -> bool:
        if run.status in TERMINAL_RUN_STATUSES:
            return False
        run.status = 'cancelling'
        turn.status = 'cancelling'
        turn.updated_at = utcnow()
        db.flush()
        return True

    def cancel_run(self, db: Session, run: Run, turn: Turn) -> None:
        run.status = 'cancelled'
        run.finished_at = utcnow()
        if turn.latest_assistant_message_id:
            turn.status = 'completed'
        else:
            turn.status = 'cancelled'
        turn.updated_at = utcnow()
        db.flush()

    def fail_run(self, db: Session, run: Run, turn: Turn, error_message: str) -> None:
        run.status = 'failed'
        run.error_message = error_message
        run.finished_at = utcnow()
        if turn.latest_assistant_message_id:
            turn.status = 'completed'
        else:
            turn.status = 'failed'
        turn.updated_at = utcnow()
        db.flush()

    def is_cancel_requested(self, run: Run) -> bool:
        return run.status == 'cancelling'
