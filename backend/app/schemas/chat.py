from __future__ import annotations

from pydantic import BaseModel, constr


QuestionStr = constr(strip_whitespace=True, min_length=1, max_length=4000)
RunIdStr = constr(strip_whitespace=True, min_length=1, max_length=64)


class SendMessageRequest(BaseModel):
    question: QuestionStr


class RegenerateTurnRequest(BaseModel):
    assistant_message_id: int


class CancelRunRequest(BaseModel):
    run_id: RunIdStr


class RouteSnapshotResponse(BaseModel):
    route: str
    confidence: float | None = None
    matched_domains: list[str] = []
    target_tables: list[str] = []
    filters: dict = {}
    reason: str = ''


class MessageMetadataResponse(BaseModel):
    route: RouteSnapshotResponse | dict
    route_reason: str = ''
    active_skill: str = ''
    sql_query: str = ''
    sql_error: str = ''
    columns: list = []
    rows: list = []
    row_count: int | None = None
    truncated: bool = False


class MessageResponse(BaseModel):
    id: int
    turn_id: int | None = None
    role: str
    content: str
    metadata: dict
    created_at: str | None = None


class TurnResponse(BaseModel):
    id: int
    sequence: int
    status: str
    user_message_id: int
    latest_assistant_message_id: int | None = None


class RunResponse(BaseModel):
    id: int
    public_id: str
    turn_id: int
    kind: str
    status: str
    current_step: str
    route: str
    route_reason: str
    sql_query: str
    error_message: str
    started_at: str | None = None
    finished_at: str | None = None


class ThreadDetailResponse(BaseModel):
    id: int
    public_id: str
    title: str
    updated_at: str | None = None
    latest_run: dict | None = None
    messages: list[MessageResponse]
    turns: list[TurnResponse]
    runs: list[RunResponse]


class ThreadSummaryResponse(BaseModel):
    id: int
    public_id: str
    title: str
    updated_at: str | None = None


class SendMessageResponse(BaseModel):
    thread_id: str
    turn_id: int
    user_message_id: int
    run_id: str
    status: str


class RegenerateResponse(BaseModel):
    thread_id: str
    turn_id: int
    run_id: str
    status: str


class CancelRunResponse(BaseModel):
    ok: bool
    run_id: str
    status: str


class DeleteThreadResponse(BaseModel):
    ok: bool
    public_id: str
