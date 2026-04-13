from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Message, Run, Thread, Turn


class ThreadRepository:
    def list_for_user(self, db: Session, user_id: int) -> list[Thread]:
        return db.query(Thread).filter(Thread.owner_id == user_id).order_by(Thread.updated_at.desc()).all()

    def get_for_user(self, db: Session, public_id: str, user_id: int) -> Thread | None:
        return db.query(Thread).filter(Thread.public_id == public_id, Thread.owner_id == user_id).first()

    def create(self, db: Session, user_id: int, title: str = "新对话") -> Thread:
        thread = Thread(owner_id=user_id, title=title)
        db.add(thread)
        db.flush()
        return thread

    def create_message(self, db: Session, *, thread_id: int, turn_id: int | None, role: str, content: str, metadata_json: str = "{}") -> Message:
        message = Message(thread_id=thread_id, turn_id=turn_id, role=role, content=content, metadata_json=metadata_json)
        db.add(message)
        db.flush()
        return message

    def create_turn(self, db: Session, *, thread_id: int, sequence: int, user_message_id: int) -> Turn:
        turn = Turn(thread_id=thread_id, sequence=sequence, status="pending", user_message_id=user_message_id)
        db.add(turn)
        db.flush()
        return turn

    def create_run(self, db: Session, *, thread_id: int, turn_id: int, kind: str) -> Run:
        run = Run(thread_id=thread_id, turn_id=turn_id, kind=kind, status="pending")
        db.add(run)
        db.flush()
        return run

    def get_run_for_thread(self, db: Session, public_run_id: str, thread_id: int) -> Run | None:
        return db.query(Run).filter(Run.public_id == public_run_id, Run.thread_id == thread_id).first()

    def list_messages_for_thread(self, db: Session, thread_id: int) -> list[Message]:
        return db.query(Message).filter(Message.thread_id == thread_id).order_by(Message.created_at.asc(), Message.id.asc()).all()

    def list_turns_for_thread(self, db: Session, thread_id: int) -> list[Turn]:
        return db.query(Turn).filter(Turn.thread_id == thread_id).order_by(Turn.sequence.asc()).all()

    def delete_thread(self, db: Session, thread: Thread) -> None:
        db.delete(thread)
