from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RouteDecision:
    route: str
    confidence: float = 0.0
    matched_domains: list[str] = field(default_factory=list)
    target_tables: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    intent: str = ""

    def to_state_update(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "route_confidence": self.confidence,
            "route_domains": self.matched_domains,
            "route_tables": self.target_tables,
            "route_reason": self.reason,
            "intent": self.intent,
        }


@dataclass(slots=True)
class SkillPlan:
    skill_name: str
    domain: str
    node_name: str
    tables: list[str] = field(default_factory=list)
    reason: str = ""

    def to_state_update(self) -> dict[str, Any]:
        return {
            "active_skill": self.skill_name,
            "active_domain": self.domain,
            "skill_tables": self.tables,
            "skill_reason": self.reason,
        }


@dataclass(slots=True)
class SkillResult:
    skill_name: str
    final_answer: str
    sql_query: str = ""
    sql_error: str = ""
    db_result: list[Any] = field(default_factory=list)
    table_columns: list[str] = field(default_factory=list)
    table_data: Any = None
    chart_data: Any = None
    row_count: int | None = None
    truncated: bool = False
    chat_history: list[str] = field(default_factory=list)

    def to_skill_update(self) -> dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "sql_query": self.sql_query,
            "sql_error": self.sql_error,
            "table_columns": self.table_columns,
            "db_result": self.db_result,
            "row_count": self.row_count,
            "truncated": self.truncated,
        }

    def to_final_update(self) -> dict[str, Any]:
        return {
            "final_answer": self.final_answer,
            "sql_query": self.sql_query,
            "sql_error": self.sql_error,
            "db_result": self.db_result,
            "table_columns": self.table_columns,
            "table_data": self.table_data,
            "chart_data": self.chart_data,
            "row_count": self.row_count,
            "truncated": self.truncated,
            "chat_history": self.chat_history,
        }


@dataclass(slots=True)
class SkillExecution:
    domain: str
    plan: SkillPlan
    result: SkillResult


class CancelledError(Exception):
    """Raised when the workflow run is cancelled."""
    pass
