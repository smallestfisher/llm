from __future__ import annotations

from pydantic import BaseModel


class ThreadSummary(BaseModel):
    id: int
    public_id: str
    title: str
    updated_at: str | None = None


class ThreadDetail(BaseModel):
    id: int
    public_id: str
    title: str
    updated_at: str | None = None
    messages: list[dict]
    turns: list[dict]
    runs: list[dict]
