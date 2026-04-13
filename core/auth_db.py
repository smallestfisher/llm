import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Sequence
from uuid import uuid4

import bcrypt
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker


logger = logging.getLogger("boe.auth")

DB_URI = os.getenv("LOCAL_DB_URI", "sqlite:///./app_local.db")
_connect_args = {"check_same_thread": False} if DB_URI.startswith("sqlite") else {}
engine = create_engine(DB_URI, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(255), default="", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    users = relationship("User", secondary=user_roles, back_populates="roles")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    last_login_at = Column(DateTime(timezone=True))

    roles = relationship("Role", secondary=user_roles, back_populates="users")
    threads = relationship("ChatThread", back_populates="owner")
    audit_logs = relationship("AuditLog", back_populates="actor")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50), default="", nullable=False)
    target_id = Column(String(100), default="", nullable=False)
    status = Column(String(30), default="success", nullable=False)
    ip_address = Column(String(64), default="", nullable=False)
    details_json = Column(Text, default="{}", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    actor = relationship("User", back_populates="audit_logs")

    @property
    def details(self) -> dict:
        try:
            return json.loads(self.details_json or "{}")
        except Exception:
            return {}


class ChatThread(Base):
    __tablename__ = "chat_threads"

    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid4()), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), default="新对话", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    owner = relationship("User", back_populates="threads")
    messages = relationship(
        "ChatMessage",
        back_populates="thread",
        order_by="ChatMessage.created_at",
        cascade="all, delete-orphan",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("chat_threads.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(Text, default="{}", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    thread = relationship("ChatThread", back_populates="messages")

    @property
    def payload(self) -> dict:
        try:
            return json.loads(self.metadata_json or "{}")
        except Exception:
            return {}


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def get_or_create_role(session, name: str, description: str = "") -> Role:
    role = session.query(Role).filter(Role.name == name).first()
    if role:
        return role
    role = Role(name=name, description=description)
    session.add(role)
    session.flush()
    return role


def set_user_roles(session, user: User, role_names: Sequence[str]) -> None:
    names = []
    for role_name in role_names:
        name = (role_name or "").strip().lower()
        if name and name not in names:
            names.append(name)
    if not names:
        names = ["user"]
    user.roles = [get_or_create_role(session, name, f"{name} role") for name in names]


def get_user_role_names(user: Optional[User]) -> list[str]:
    if not user:
        return []
    return sorted(role.name for role in user.roles)


def user_has_role(user: Optional[User], *role_names: str) -> bool:
    current = set(get_user_role_names(user))
    return any(role_name in current for role_name in role_names)


def create_user(
    session,
    username: str,
    password: str,
    role_names: Optional[Sequence[str]] = None,
    is_active: bool = True,
) -> User:
    existing = session.query(User).filter(User.username == username).first()
    if existing:
        raise ValueError(f"用户 {username} 已存在")
    user = User(username=username.strip(), password_hash=hash_password(password), is_active=is_active)
    session.add(user)
    session.flush()
    set_user_roles(session, user, role_names or ["user"])
    session.flush()
    return user


def change_password(session, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    user.updated_at = utcnow()
    session.flush()


def log_audit(
    session,
    *,
    action: str,
    actor: Optional[User] = None,
    target_type: str = "",
    target_id: str = "",
    status: str = "success",
    ip_address: str = "",
    details: Optional[dict] = None,
) -> AuditLog:
    log = AuditLog(
        actor_id=actor.id if actor else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id or ""),
        status=status,
        ip_address=ip_address or "",
        details_json=json.dumps(details or {}, ensure_ascii=False),
    )
    session.add(log)
    session.flush()
    return log


def append_chat_message(
    session,
    thread: ChatThread,
    role: str,
    content: str,
    metadata: Optional[dict] = None,
) -> ChatMessage:
    message = ChatMessage(
        thread_id=thread.id,
        role=role,
        content=content,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
    )
    thread.updated_at = utcnow()
    if role == "user" and thread.title == "新对话":
        thread.title = content.strip().replace("\n", " ")[:48] or "新对话"
    session.add(message)
    session.flush()
    return message


def build_seed_history(thread: ChatThread) -> list[str]:
    history = []
    pending_question: Optional[str] = None
    for message in thread.messages:
        if message.role == "user":
            pending_question = message.content
            continue
        if message.role == "assistant" and pending_question:
            history.append(f"问: {pending_question}\n答: {message.content}")
            pending_question = None
    return history


def list_thread_messages(session, thread: ChatThread) -> list[ChatMessage]:
    return (
        session.query(ChatMessage)
        .filter(ChatMessage.thread_id == thread.id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )


def build_history_from_messages(messages: Sequence[ChatMessage]) -> list[str]:
    history = []
    pending_question: Optional[str] = None
    for message in messages:
        if message.role == "user":
            pending_question = message.content
            continue
        if message.role == "assistant" and pending_question:
            history.append(f"问: {pending_question}\n答: {message.content}")
            pending_question = None
    return history


def get_last_user_message(session, thread: ChatThread) -> Optional[ChatMessage]:
    return (
        session.query(ChatMessage)
        .filter(ChatMessage.thread_id == thread.id, ChatMessage.role == "user")
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .first()
    )


def get_last_assistant_message(session, thread: ChatThread) -> Optional[ChatMessage]:
    return (
        session.query(ChatMessage)
        .filter(ChatMessage.thread_id == thread.id, ChatMessage.role == "assistant")
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .first()
    )


def build_regenerate_seed_history(session, thread: ChatThread) -> tuple[list[str], Optional[ChatMessage], Optional[ChatMessage]]:
    messages = list_thread_messages(session, thread)
    last_user_index = None
    last_assistant_index = None
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if last_assistant_index is None and message.role == "assistant":
            last_assistant_index = index
            continue
        if message.role == "user":
            last_user_index = index
            break

    if last_user_index is None:
        return [], None, None

    last_user = messages[last_user_index]
    if last_assistant_index is None or last_assistant_index < last_user_index:
        return build_history_from_messages(messages[:last_user_index]), last_user, None

    history = build_history_from_messages(messages[:last_user_index])
    return history, last_user, messages[last_assistant_index]


def init_local_db() -> None:
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    if inspector.has_table("chat_messages"):
        columns = {col["name"] for col in inspector.get_columns("chat_messages")}
        if "metadata_json" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE chat_messages ADD COLUMN metadata_json TEXT DEFAULT '{}' NOT NULL"))
    session = SessionLocal()
    try:
        get_or_create_role(session, "admin", "系统管理员")
        get_or_create_role(session, "user", "普通用户")
        session.flush()
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


try:
    init_local_db()
except Exception as exc:
    logger.warning("Skip auth_db initialization during import: %s", exc)
