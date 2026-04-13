from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TurnStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class RunKind(str, Enum):
    initial = "initial"
    regenerate = "regenerate"


class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    cancelling = "cancelling"
    cancelled = "cancelled"
    failed = "failed"
    completed = "completed"


@dataclass(slots=True)
class ThreadEntity:
    id: str
    owner_id: str
    title: str
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class MessageEntity:
    id: str
    thread_id: str
    turn_id: str | None
    role: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass(slots=True)
class TurnEntity:
    id: str
    thread_id: str
    user_message_id: str
    latest_assistant_message_id: str | None
    status: TurnStatus
    sequence: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class RunEntity:
    id: str
    thread_id: str
    turn_id: str
    kind: RunKind
    status: RunStatus
    current_step: str
    route: str
    route_reason: str
    sql_query: str
    error_message: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
