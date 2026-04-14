from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Message, Run, Thread, Turn, utcnow


class ThreadService:
    def list_threads_for_user(self, db: Session, user_id: int) -> list[Thread]:
        return db.query(Thread).filter(Thread.owner_id == user_id).order_by(Thread.updated_at.desc()).all()

    def create_thread(self, db: Session, user_id: int, title: str = "新对话") -> Thread:
        thread = Thread(owner_id=user_id, title=title)
        db.add(thread)
        db.flush()
        return thread

    def delete_thread(self, db: Session, thread: Thread) -> None:
        db.delete(thread)

    def get_thread_for_user(self, db: Session, user_id: int, public_id: str) -> Thread | None:
        return db.query(Thread).filter(Thread.owner_id == user_id, Thread.public_id == public_id).first()

    def list_thread_turns(self, db: Session, thread_id: int) -> list[Turn]:
        return db.query(Turn).filter(Turn.thread_id == thread_id).order_by(Turn.sequence.asc()).all()

    def get_latest_turn(self, db: Session, thread_id: int) -> Turn | None:
        return db.query(Turn).filter(Turn.thread_id == thread_id).order_by(Turn.sequence.desc()).first()

    def list_thread_messages(self, db: Session, thread_id: int) -> list[Message]:
        return db.query(Message).filter(Message.thread_id == thread_id).order_by(Message.created_at.asc(), Message.id.asc()).all()

    def get_message_by_id(self, db: Session, thread_id: int, message_id: int) -> Message | None:
        return db.query(Message).filter(Message.thread_id == thread_id, Message.id == message_id).first()

    def get_turn_by_id(self, db: Session, thread_id: int, turn_id: int) -> Turn | None:
        return db.query(Turn).filter(Turn.thread_id == thread_id, Turn.id == turn_id).first()

    def get_run_by_public_id(self, db: Session, thread_id: int, public_id: str) -> Run | None:
        return db.query(Run).filter(Run.thread_id == thread_id, Run.public_id == public_id).first()

    def list_runs(self, db: Session, thread_id: int) -> list[Run]:
        return db.query(Run).filter(Run.thread_id == thread_id).all()

    def get_latest_run(self, db: Session, turn_id: int) -> Run | None:
        return db.query(Run).filter(Run.turn_id == turn_id).order_by(Run.started_at.desc(), Run.id.desc()).first()

    def delete_runs_for_turn(self, db: Session, turn_id: int) -> None:
        db.query(Run).filter(Run.turn_id == turn_id).delete()
        db.flush()

    def append_user_turn(self, db: Session, thread: Thread, question: str) -> tuple[Turn, Message]:
        sequence = self.list_thread_turns(db, thread.id)
        next_sequence = len(sequence) + 1
        user_message = Message(thread_id=thread.id, role="user", content=question)
        db.add(user_message)
        db.flush()
        turn = Turn(thread_id=thread.id, sequence=next_sequence, status="pending", user_message_id=user_message.id)
        db.add(turn)
        db.flush()
        user_message.turn_id = turn.id
        self.set_thread_title_from_turn(thread, question)
        db.flush()
        return turn, user_message

    def append_assistant_message(self, db: Session, turn: Turn, content: str, metadata_json: str) -> Message:
        message = Message(
            thread_id=turn.thread_id,
            turn_id=turn.id,
            role="assistant",
            content=content,
            metadata_json=metadata_json,
        )
        db.add(message)
        db.flush()
        turn.latest_assistant_message_id = message.id
        turn.status = "completed"
        turn.updated_at = utcnow()
        db.flush()
        return message

    def delete_assistant_message_for_turn(self, db: Session, turn: Turn) -> None:
        if turn.latest_assistant_message_id:
            message = db.query(Message).filter(Message.id == turn.latest_assistant_message_id).first()
            if message:
                db.delete(message)
                db.flush()
        turn.latest_assistant_message_id = None
        turn.status = "pending"
        turn.updated_at = utcnow()
        db.flush()

    def mark_turn_completed(self, db: Session, turn: Turn) -> None:
        turn.status = "completed"
        turn.updated_at = utcnow()
        db.flush()

    def mark_turn_failed(self, db: Session, turn: Turn) -> None:
        turn.status = "failed"
        turn.updated_at = utcnow()
        db.flush()

    def mark_turn_cancelled(self, db: Session, turn: Turn) -> None:
        turn.status = "cancelled"
        turn.updated_at = utcnow()
        db.flush()

    def set_thread_title_from_turn(self, thread: Thread, question: str) -> None:
        if thread.title == "新对话":
            thread.title = question.strip().replace("\n", " ")[:48] or "新对话"
        thread.updated_at = utcnow()

    def set_thread_updated(self, db: Session, thread: Thread) -> None:
        thread.updated_at = utcnow()
        db.flush()

    def rename_thread(self, db: Session, thread: Thread, title: str) -> Thread:
        thread.title = title.strip() or thread.title
        thread.updated_at = utcnow()
        db.flush()
        return thread

    def get_role_names(self, user) -> list[str]:
        return [role.name for role in user.roles]

    def is_admin(self, user) -> bool:
        return "admin" in self.get_role_names(user)
