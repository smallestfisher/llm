from __future__ import annotations

import os
import re
from datetime import date, datetime
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from app.execution.sql_guard import lint_sql
from app.logging_config import get_logger


logger = get_logger("boe.runtime")
SAMPLE_LIMIT = int(os.getenv("SAMPLE_LIMIT", "5000"))
AUTO_TRUNCATE_ROWS = int(os.getenv("AUTO_TRUNCATE_ROWS", "50000"))
SQL_ENABLE_PRECOUNT = os.getenv("SQL_ENABLE_PRECOUNT", "0") == "1"
SQL_CANDIDATE_PROBE_LIMIT = int(os.getenv("SQL_CANDIDATE_PROBE_LIMIT", "1"))

load_dotenv()


class Database:
    def __init__(self, uri: str):
        self.engine = create_engine(uri)

    def run(self, sql: str):
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            if not result.returns_rows:
                return [], []
            columns = list(result.keys())
            if not columns:
                cursor = getattr(result, "cursor", None)
                description = getattr(cursor, "description", None) if cursor is not None else None
                if description:
                    columns = [item[0] for item in description if item and item[0]]
            rows = result.fetchall()
            return [tuple(row) for row in rows], columns


def get_db_connection() -> Database:
    db_uri = os.getenv("DB_URI")
    if not db_uri:
        raise ValueError("请在 .env 文件中配置 DB_URI")
    return Database(db_uri)


_db = get_db_connection()


def _has_limit_clause(sql: str) -> bool:
    return bool(re.search(r"(?is)\blimit\s+\d+(\s*,\s*\d+)?\s*$", sql.strip()))


def _build_probe_sql(sql: str, *, probe_limit: int) -> str:
    candidate = (sql or "").strip()
    if not candidate:
        return candidate
    if _has_limit_clause(candidate):
        return candidate
    lower_sql = candidate.lower()
    if not (lower_sql.startswith("select") or lower_sql.startswith("with")):
        return candidate
    return f"{candidate} LIMIT {max(1, probe_limit)}"


def choose_best_sql_candidate(
    candidates: list[str],
    *,
    question: str = "",
    domain: str = "",
    structured_filters: dict[str, Any] | None = None,
    allowed_tables: list[str] | None = None,
    query_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    seen: set[str] = set()
    ordered_candidates: list[str] = []
    for sql in candidates:
        normalized = (sql or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered_candidates.append(normalized)

    if not ordered_candidates:
        return {"best_sql": "", "reports": []}

    reports: list[dict[str, Any]] = []
    for index, sql in enumerate(ordered_candidates):
        lint_issues = lint_sql(
            sql,
            question=question,
            domain=domain,
            structured_filters=structured_filters,
            allowed_tables=allowed_tables,
            query_state=query_state,
        )
        score = 0
        probe_ok = False
        probe_error = ""
        probe_rows = 0

        if lint_issues:
            score = -100 - (5 * len(lint_issues))
        else:
            score += 50
            probe_sql = _build_probe_sql(sql, probe_limit=SQL_CANDIDATE_PROBE_LIMIT)
            try:
                rows, _ = _db.run(probe_sql)
                probe_rows = len(rows)
                probe_ok = True
                score += 40
                if probe_rows > 0:
                    score += 5
            except Exception as exc:
                probe_error = str(exc)
                score -= 20

        reports.append(
            {
                "index": index,
                "sql": sql,
                "score": score,
                "lint_issues": lint_issues,
                "probe_ok": probe_ok,
                "probe_rows": probe_rows,
                "probe_error": probe_error,
            }
        )

    reports.sort(key=lambda item: item["score"], reverse=True)
    best_sql = reports[0]["sql"] if reports else ordered_candidates[0]
    best_report = reports[0] if reports else {}
    return {
        "best_sql": best_sql,
        "best_score": int(best_report.get("score", -999)),
        "best_probe_ok": bool(best_report.get("probe_ok")),
        "best_lint_issues": list(best_report.get("lint_issues") or []),
        "reports": reports,
    }


def execute_sql(
    sql: str,
    *,
    question: str = "",
    domain: str = "",
    structured_filters: dict[str, Any] | None = None,
    allowed_tables: list[str] | None = None,
    query_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not sql:
        return {"db_result": [], "sql_error": "SQL 为空", "table_columns": [], "row_count": None, "truncated": False}

    lint_issues = lint_sql(
        sql,
        question=question,
        domain=domain,
        structured_filters=structured_filters,
        allowed_tables=allowed_tables,
        query_state=query_state,
    )
    if lint_issues:
        return {
            "db_result": [],
            "sql_error": "SQL lint failed: " + "；".join(lint_issues),
            "table_columns": [],
            "row_count": None,
            "truncated": False,
        }

    try:
        lower_sql = sql.lower()
        is_select = lower_sql.strip().startswith("select") or lower_sql.strip().startswith("with")
        is_aggregate = (" group by " in lower_sql) or any(
            token in lower_sql for token in ("count(", "sum(", "avg(", "min(", "max(")
        )
        has_limit = bool(re.search(r"(?is)\blimit\s+\d+(\s*,\s*\d+)?\s*$", sql))

        row_count = None
        truncated = False
        effective_sql = sql
        if is_select and not is_aggregate:
            if SQL_ENABLE_PRECOUNT and not has_limit:
                base_sql = re.sub(r"\s+limit\s+\d+(\s*,\s*\d+)?\s*$", "", sql, flags=re.IGNORECASE).strip()
                count_sql = f"SELECT COUNT(*) FROM ({base_sql}) AS subq"
                try:
                    count_rows, _ = _db.run(count_sql)
                    if count_rows and isinstance(count_rows[0], (list, tuple)):
                        row_count = int(count_rows[0][0])
                except Exception:
                    row_count = None
                if row_count is not None and row_count > AUTO_TRUNCATE_ROWS:
                    effective_sql = f"{sql} LIMIT {SAMPLE_LIMIT}"
                    truncated = True
            elif not has_limit:
                effective_sql = f"{sql} LIMIT {SAMPLE_LIMIT}"
                truncated = True

        rows, columns = _db.run(effective_sql)
        formatted_rows: list[list[Any]] = []
        for row in rows:
            new_row: list[Any] = []
            for item in row:
                if isinstance(item, (date, datetime)):
                    new_row.append(item.strftime("%Y-%m-%d"))
                else:
                    new_row.append(item)
            formatted_rows.append(new_row)

        if row_count is None:
            row_count = len(formatted_rows)

        return {
            "db_result": formatted_rows,
            "sql_error": "",
            "table_columns": columns,
            "row_count": row_count,
            "truncated": truncated,
        }
    except Exception as exc:
        logger.error("SQL Execution Error: {}", exc)
        return {
            "db_result": [],
            "sql_error": str(exc),
            "table_columns": [],
            "row_count": None,
            "truncated": False,
        }
