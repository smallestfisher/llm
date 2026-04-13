from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import relationship

from app.db import Base


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
    threads = relationship("Thread", back_populates="owner")
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


class Thread(Base):
    __tablename__ = "threads"

    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid4()), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), default="新对话", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    owner = relationship("User", back_populates="threads")
    turns = relationship("Turn", back_populates="thread", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="thread", cascade="all, delete-orphan")
    runs = relationship("Run", back_populates="thread", cascade="all, delete-orphan")


class Turn(Base):
    __tablename__ = "turns"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    status = Column(String(20), default="pending", nullable=False)
    user_message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    latest_assistant_message_id = Column(Integer, ForeignKey("messages.id"))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    thread = relationship("Thread", back_populates="turns")
    user_message = relationship("Message", foreign_keys=[user_message_id])
    latest_assistant_message = relationship("Message", foreign_keys=[latest_assistant_message_id])
    runs = relationship("Run", back_populates="turn", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=False, index=True)
    turn_id = Column(Integer, ForeignKey("turns.id"), index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(Text, default="{}", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    thread = relationship("Thread", back_populates="messages")

    @property
    def metadata_dict(self) -> dict:
        try:
            return json.loads(self.metadata_json or "{}")
        except Exception:
            return {}


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid4()), nullable=False)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=False, index=True)
    turn_id = Column(Integer, ForeignKey("turns.id"), nullable=False, index=True)
    kind = Column(String(20), default="initial", nullable=False)
    status = Column(String(20), default="pending", nullable=False)
    current_step = Column(String(40), default="", nullable=False)
    route = Column(String(40), default="", nullable=False)
    route_reason = Column(Text, default="", nullable=False)
    sql_query = Column(Text, default="", nullable=False)
    error_message = Column(Text, default="", nullable=False)
    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at = Column(DateTime(timezone=True))

    thread = relationship("Thread", back_populates="runs")
    turn = relationship("Turn", back_populates="runs")
