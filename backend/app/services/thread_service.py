from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Message, Thread, Turn, utcnow


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

    def append_user_turn(self, db: Session, thread: Thread, question: str) -> tuple[Turn, Message]:
        next_sequence = db.query(Turn).filter(Turn.thread_id == thread.id).count() + 1
        user_message = Message(thread_id=thread.id, role="user", content=question)
        db.add(user_message)
        db.flush()
        turn = Turn(thread_id=thread.id, sequence=next_sequence, status="pending", user_message_id=user_message.id)
        db.add(turn)
        db.flush()
        user_message.turn_id = turn.id
        if thread.title == "新对话":
            thread.title = question.strip().replace("\n", " ")[:48] or "新对话"
        thread.updated_at = utcnow()
        db.flush()
        return turn, user_message

    def get_thread_for_user(self, db: Session, user_id: int, public_id: str) -> Thread | None:
        return db.query(Thread).filter(Thread.owner_id == user_id, Thread.public_id == public_id).first()

    def get_latest_turn(self, db: Session, thread_id: int) -> Turn | None:
        return db.query(Turn).filter(Turn.thread_id == thread_id).order_by(Turn.sequence.desc()).first()

    def list_thread_messages(self, db: Session, thread_id: int) -> list[Message]:
        return db.query(Message).filter(Message.thread_id == thread_id).order_by(Message.created_at.asc(), Message.id.asc()).all()

    def list_thread_turns(self, db: Session, thread_id: int) -> list[Turn]:
        return db.query(Turn).filter(Turn.thread_id == thread_id).order_by(Turn.sequence.asc()).all()

    def append_assistant_message(self, db: Session, turn: Turn, content: str, metadata_json: str) -> Message:
        message = Message(thread_id=turn.thread_id, turn_id=turn.id, role="assistant", content=content, metadata_json=metadata_json)
        db.add(message)
        db.flush()
        turn.latest_assistant_message_id = message.id
        turn.status = "completed"
        turn.updated_at = utcnow()
        db.flush()
        return message

    def mark_turn_cancelled(self, db: Session, turn: Turn) -> None:
        turn.status = "cancelled"
        turn.updated_at = utcnow()
        db.flush()

    def mark_turn_failed(self, db: Session, turn: Turn) -> None:
        turn.status = "failed"
        turn.updated_at = utcnow()
        db.flush()

    def set_thread_title_from_turn(self, thread: Thread, question: str) -> None:
        if thread.title == "新对话":
            thread.title = question.strip().replace("\n", " ")[:48] or "新对话"
        thread.updated_at = utcnow()

    def touch_thread(self, thread: Thread) -> None:
        thread.updated_at = utcnow()

    def get_next_turn_sequence(self, db: Session, thread_id: int) -> int:
        return db.query(Turn).filter(Turn.thread_id == thread_id).count() + 1

    def get_message_by_id(self, db: Session, thread_id: int, message_id: int) -> Message | None:
        return db.query(Message).filter(Message.thread_id == thread_id, Message.id == message_id).first()

    def get_turn_by_id(self, db: Session, thread_id: int, turn_id: int) -> Turn | None:
        return db.query(Turn).filter(Turn.thread_id == thread_id, Turn.id == turn_id).first()

    def remove_message(self, db: Session, message: Message) -> None:
        db.delete(message)

    def get_run_by_public_id(self, db: Session, thread_id: int, public_id: str):
        return db.query(__import__('app.models', fromlist=['Run']).Run).filter_by(thread_id=thread_id, public_id=public_id).first()

    def list_runs(self, db: Session, thread_id: int):
        return db.query(__import__('app.models', fromlist=['Run']).Run).filter_by(thread_id=thread_id).all()

    def delete_runs_for_turn(self, db: Session, turn_id: int) -> None:
        RunModel = __import__('app.models', fromlist=['Run']).Run
        db.query(RunModel).filter(RunModel.turn_id == turn_id).delete()
        db.flush()

    def get_latest_run(self, db: Session, turn_id: int):
        RunModel = __import__('app.models', fromlist=['Run']).Run
        return db.query(RunModel).filter(RunModel.turn_id == turn_id).order_by(RunModel.started_at.desc(), RunModel.id.desc()).first()

    def set_thread_updated(self, db: Session, thread: Thread) -> None:
        thread.updated_at = utcnow()
        db.flush()

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

    def get_role_names(self, user) -> list[str]:
        return [role.name for role in user.roles]

    def is_admin(self, user) -> bool:
        return 'admin' in self.get_role_names(user)

    def count_threads_for_user(self, db: Session, user_id: int) -> int:
        return db.query(Thread).filter(Thread.owner_id == user_id).count()

    def count_messages_for_thread(self, db: Session, thread_id: int) -> int:
        return db.query(Message).filter(Message.thread_id == thread_id).count()

    def count_turns_for_thread(self, db: Session, thread_id: int) -> int:
        return db.query(Turn).filter(Turn.thread_id == thread_id).count()

    def count_runs_for_thread(self, db: Session, thread_id: int) -> int:
        RunModel = __import__('app.models', fromlist=['Run']).Run
        return db.query(RunModel).filter(RunModel.thread_id == thread_id).count()

    def list_thread_public_ids(self, db: Session, user_id: int) -> list[str]:
        return [row.public_id for row in self.list_threads_for_user(db, user_id)]

    def get_user_thread_titles(self, db: Session, user_id: int) -> list[str]:
        return [row.title for row in self.list_threads_for_user(db, user_id)]

    def rename_thread(self, db: Session, thread: Thread, title: str) -> Thread:
        thread.title = title.strip() or thread.title
        thread.updated_at = utcnow()
        db.flush()
        return thread

    def latest_assistant_content(self, turn: Turn) -> str:
        if not turn.latest_assistant_message:
            return ''
        return turn.latest_assistant_message.content

    def user_question_content(self, turn: Turn) -> str:
        if not turn.user_message:
            return ''
        return turn.user_message.content

    def get_turn_history_pairs(self, db: Session, thread_id: int) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for turn in self.list_thread_turns(db, thread_id):
            if turn.user_message and turn.latest_assistant_message:
                pairs.append((turn.user_message.content, turn.latest_assistant_message.content))
        return pairs

    def has_any_threads(self, db: Session, user_id: int) -> bool:
        return self.count_threads_for_user(db, user_id) > 0

    def has_any_messages(self, db: Session, thread_id: int) -> bool:
        return self.count_messages_for_thread(db, thread_id) > 0

    def latest_thread_for_user(self, db: Session, user_id: int) -> Thread | None:
        rows = self.list_threads_for_user(db, user_id)
        return rows[0] if rows else None

    def latest_turn_for_thread(self, db: Session, thread_id: int) -> Turn | None:
        return self.get_latest_turn(db, thread_id)

    def latest_run_for_turn(self, db: Session, turn_id: int):
        return self.get_latest_run(db, turn_id)

    def clear_turn_assistant(self, db: Session, turn: Turn) -> None:
        self.delete_assistant_message_for_turn(db, turn)

    def restore_turn_pending(self, db: Session, turn: Turn) -> None:
        turn.status = "pending"
        turn.updated_at = utcnow()
        db.flush()

    def mark_turn_completed(self, db: Session, turn: Turn) -> None:
        turn.status = "completed"
        turn.updated_at = utcnow()
        db.flush()

    def attach_message_to_turn(self, db: Session, message: Message, turn: Turn) -> Message:
        message.turn_id = turn.id
        db.flush()
        return message

    def create_empty_thread_if_missing(self, db: Session, user_id: int) -> Thread:
        thread = self.latest_thread_for_user(db, user_id)
        if thread:
            return thread
        return self.create_thread(db, user_id)

    def get_thread_or_raise(self, db: Session, user_id: int, public_id: str) -> Thread:
        thread = self.get_thread_for_user(db, user_id, public_id)
        if not thread:
            raise ValueError('thread not found')
        return thread

    def get_turn_or_none(self, db: Session, thread_id: int, turn_id: int) -> Turn | None:
        return self.get_turn_by_id(db, thread_id, turn_id)

    def get_message_or_none(self, db: Session, thread_id: int, message_id: int) -> Message | None:
        return self.get_message_by_id(db, thread_id, message_id)

    def update_thread_title(self, db: Session, thread: Thread, title: str) -> Thread:
        return self.rename_thread(db, thread, title)

    def reset_thread_timestamp(self, db: Session, thread: Thread) -> None:
        thread.updated_at = utcnow()
        db.flush()

    def get_all_thread_rows(self, db: Session) -> list[Thread]:
        return db.query(Thread).order_by(Thread.updated_at.desc()).all()

    def get_all_turn_rows(self, db: Session) -> list[Turn]:
        return db.query(Turn).order_by(Turn.updated_at.desc()).all()

    def get_all_message_rows(self, db: Session) -> list[Message]:
        return db.query(Message).order_by(Message.created_at.desc()).all()

    def get_role_names_for_user(self, user) -> list[str]:
        return self.get_role_names(user)

    def user_is_admin(self, user) -> bool:
        return self.is_admin(user)

    def touch(self, db: Session, thread: Thread) -> None:
        self.set_thread_updated(db, thread)

    def seed_title(self, thread: Thread, question: str) -> None:
        self.set_thread_title_from_turn(thread, question)

    def create_turn_and_user_message(self, db: Session, thread: Thread, question: str) -> tuple[Turn, Message]:
        return self.append_user_turn(db, thread, question)

    def remove_thread(self, db: Session, thread: Thread) -> None:
        self.delete_thread(db, thread)

    def all_user_threads(self, db: Session, user_id: int) -> list[Thread]:
        return self.list_threads_for_user(db, user_id)

    def find_thread(self, db: Session, user_id: int, public_id: str) -> Thread | None:
        return self.get_thread_for_user(db, user_id, public_id)

    def find_turn(self, db: Session, thread_id: int, turn_id: int) -> Turn | None:
        return self.get_turn_by_id(db, thread_id, turn_id)

    def find_message(self, db: Session, thread_id: int, message_id: int) -> Message | None:
        return self.get_message_by_id(db, thread_id, message_id)

    def append_assistant(self, db: Session, turn: Turn, content: str, metadata_json: str) -> Message:
        return self.append_assistant_message(db, turn, content, metadata_json)

    def clear_assistant_for_turn(self, db: Session, turn: Turn) -> None:
        self.delete_assistant_message_for_turn(db, turn)

    def pending_turn(self, db: Session, turn: Turn) -> None:
        self.restore_turn_pending(db, turn)

    def completed_turn(self, db: Session, turn: Turn) -> None:
        self.mark_turn_completed(db, turn)

    def failed_turn(self, db: Session, turn: Turn) -> None:
        self.mark_turn_failed(db, turn)

    def cancelled_turn(self, db: Session, turn: Turn) -> None:
        self.mark_turn_cancelled(db, turn)

    def title_candidates(self, db: Session, user_id: int) -> list[str]:
        return self.get_user_thread_titles(db, user_id)

    def thread_ids(self, db: Session, user_id: int) -> list[str]:
        return self.list_thread_public_ids(db, user_id)

    def turn_history(self, db: Session, thread_id: int) -> list[tuple[str, str]]:
        return self.get_turn_history_pairs(db, thread_id)

    def messages_for_thread(self, db: Session, thread_id: int) -> list[Message]:
        return self.list_thread_messages(db, thread_id)

    def turns_for_thread(self, db: Session, thread_id: int) -> list[Turn]:
        return self.list_thread_turns(db, thread_id)

    def latest_thread(self, db: Session, user_id: int) -> Thread | None:
        return self.latest_thread_for_user(db, user_id)

    def latest_turn(self, db: Session, thread_id: int) -> Turn | None:
        return self.latest_turn_for_thread(db, thread_id)

    def thread_message_count(self, db: Session, thread_id: int) -> int:
        return self.count_messages_for_thread(db, thread_id)

    def thread_turn_count(self, db: Session, thread_id: int) -> int:
        return self.count_turns_for_thread(db, thread_id)

    def thread_run_count(self, db: Session, thread_id: int) -> int:
        return self.count_runs_for_thread(db, thread_id)

    def user_thread_count(self, db: Session, user_id: int) -> int:
        return self.count_threads_for_user(db, user_id)

    def has_threads(self, db: Session, user_id: int) -> bool:
        return self.has_any_threads(db, user_id)

    def has_messages(self, db: Session, thread_id: int) -> bool:
        return self.has_any_messages(db, thread_id)

    def ensure_thread(self, db: Session, user_id: int) -> Thread:
        return self.create_empty_thread_if_missing(db, user_id)

    def require_thread(self, db: Session, user_id: int, public_id: str) -> Thread:
        return self.get_thread_or_raise(db, user_id, public_id)

    def role_names(self, user) -> list[str]:
        return self.get_role_names(user)

    def admin(self, user) -> bool:
        return self.is_admin(user)

    def latest_answer(self, turn: Turn) -> str:
        return self.latest_assistant_content(turn)

    def user_question(self, turn: Turn) -> str:
        return self.user_question_content(turn)

    def attach_turn_to_message(self, db: Session, message: Message, turn: Turn) -> Message:
        return self.attach_message_to_turn(db, message, turn)

    def next_turn_sequence(self, db: Session, thread_id: int) -> int:
        return self.get_next_turn_sequence(db, thread_id)

    def thread_touch(self, db: Session, thread: Thread) -> None:
        self.touch(db, thread)

    def thread_seed_title(self, thread: Thread, question: str) -> None:
        self.seed_title(thread, question)

    def delete_turn_runs(self, db: Session, turn_id: int) -> None:
        self.delete_runs_for_turn(db, turn_id)

    def latest_run(self, db: Session, turn_id: int):
        return self.latest_run_for_turn(db, turn_id)

    def run_by_public_id(self, db: Session, thread_id: int, public_id: str):
        return self.get_run_by_public_id(db, thread_id, public_id)

    def runs_for_thread(self, db: Session, thread_id: int):
        return self.list_runs(db, thread_id)

    def thread_rows(self, db: Session) -> list[Thread]:
        return self.get_all_thread_rows(db)

    def turn_rows(self, db: Session) -> list[Turn]:
        return self.get_all_turn_rows(db)

    def message_rows(self, db: Session) -> list[Message]:
        return self.get_all_message_rows(db)

    def thread_title_update(self, db: Session, thread: Thread, title: str) -> Thread:
        return self.update_thread_title(db, thread, title)

    def reset_thread_updated(self, db: Session, thread: Thread) -> None:
        self.reset_thread_timestamp(db, thread)

    def user_thread_titles(self, db: Session, user_id: int) -> list[str]:
        return self.title_candidates(db, user_id)

    def user_thread_public_ids(self, db: Session, user_id: int) -> list[str]:
        return self.thread_ids(db, user_id)

    def history_pairs(self, db: Session, thread_id: int) -> list[tuple[str, str]]:
        return self.turn_history(db, thread_id)

    def latest_run_for_turn_id(self, db: Session, turn_id: int):
        return self.latest_run(db, turn_id)

    def remove_assistant_for_turn(self, db: Session, turn: Turn) -> None:
        self.clear_assistant_for_turn(db, turn)

    def restore_pending(self, db: Session, turn: Turn) -> None:
        self.pending_turn(db, turn)

    def mark_completed(self, db: Session, turn: Turn) -> None:
        self.completed_turn(db, turn)

    def mark_failed(self, db: Session, turn: Turn) -> None:
        self.failed_turn(db, turn)

    def mark_cancelled(self, db: Session, turn: Turn) -> None:
        self.cancelled_turn(db, turn)

    def get_run(self, db: Session, thread_id: int, public_id: str):
        return self.run_by_public_id(db, thread_id, public_id)

    def get_runs(self, db: Session, thread_id: int):
        return self.runs_for_thread(db, thread_id)

    def delete_turn_run_rows(self, db: Session, turn_id: int) -> None:
        self.delete_turn_runs(db, turn_id)

    def latest_run_row(self, db: Session, turn_id: int):
        return self.latest_run_for_turn_id(db, turn_id)

    def find_latest_thread(self, db: Session, user_id: int) -> Thread | None:
        return self.latest_thread(db, user_id)

    def all_threads(self, db: Session) -> list[Thread]:
        return self.thread_rows(db)

    def all_turns(self, db: Session) -> list[Turn]:
        return self.turn_rows(db)

    def all_messages(self, db: Session) -> list[Message]:
        return self.message_rows(db)

    def user_roles(self, user) -> list[str]:
        return self.role_names(user)

    def is_user_admin(self, user) -> bool:
        return self.admin(user)

    def latest_thread_row(self, db: Session, user_id: int) -> Thread | None:
        return self.find_latest_thread(db, user_id)

    def assistant_message(self, db: Session, turn: Turn, content: str, metadata_json: str) -> Message:
        return self.append_assistant(db, turn, content, metadata_json)

    def user_message_and_turn(self, db: Session, thread: Thread, question: str) -> tuple[Turn, Message]:
        return self.create_turn_and_user_message(db, thread, question)

    def remove_thread_row(self, db: Session, thread: Thread) -> None:
        self.remove_thread(db, thread)

    def lookup_thread(self, db: Session, user_id: int, public_id: str) -> Thread | None:
        return self.find_thread(db, user_id, public_id)

    def lookup_turn(self, db: Session, thread_id: int, turn_id: int) -> Turn | None:
        return self.find_turn(db, thread_id, turn_id)

    def lookup_message(self, db: Session, thread_id: int, message_id: int) -> Message | None:
        return self.find_message(db, thread_id, message_id)

    def existing_history(self, db: Session, thread_id: int) -> list[tuple[str, str]]:
        return self.history_pairs(db, thread_id)

    def thread_messages(self, db: Session, thread_id: int) -> list[Message]:
        return self.messages_for_thread(db, thread_id)

    def thread_turns(self, db: Session, thread_id: int) -> list[Turn]:
        return self.turns_for_thread(db, thread_id)

    def rename(self, db: Session, thread: Thread, title: str) -> Thread:
        return self.rename_thread(db, thread, title)

    def update_timestamp(self, db: Session, thread: Thread) -> None:
        self.set_thread_updated(db, thread)

    def message_count(self, db: Session, thread_id: int) -> int:
        return self.thread_message_count(db, thread_id)

    def turn_count(self, db: Session, thread_id: int) -> int:
        return self.thread_turn_count(db, thread_id)

    def run_count(self, db: Session, thread_id: int) -> int:
        return self.thread_run_count(db, thread_id)

    def thread_count(self, db: Session, user_id: int) -> int:
        return self.user_thread_count(db, user_id)
