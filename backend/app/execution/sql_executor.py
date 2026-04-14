from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from app.execution.sql_guard import lint_sql


logger = logging.getLogger("boe.runtime")
SAMPLE_LIMIT = int(os.getenv("SAMPLE_LIMIT", "5000"))
AUTO_TRUNCATE_ROWS = int(os.getenv("AUTO_TRUNCATE_ROWS", "50000"))

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


def execute_sql(
    sql: str,
    *,
    question: str = "",
    domain: str = "",
    structured_filters: dict[str, Any] | None = None,
    allowed_tables: list[str] | None = None,
) -> dict[str, Any]:
    if not sql:
        return {"db_result": [], "sql_error": "SQL 为空", "table_columns": [], "row_count": None, "truncated": False}

    lint_issues = lint_sql(
        sql,
        question=question,
        domain=domain,
        structured_filters=structured_filters,
        allowed_tables=allowed_tables,
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

        row_count = None
        truncated = False
        effective_sql = sql
        if is_select and not is_aggregate:
            base_sql = re.sub(r"\s+limit\s+\d+(\s*,\s*\d+)?\s*$", "", sql, flags=re.IGNORECASE).strip()
            count_sql = f"SELECT COUNT(*) FROM ({base_sql}) AS subq"
            try:
                count_rows, _ = _db.run(count_sql)
                if count_rows and isinstance(count_rows[0], (list, tuple)):
                    row_count = int(count_rows[0][0])
            except Exception:
                row_count = None
            if row_count is not None and row_count > AUTO_TRUNCATE_ROWS and " limit " not in lower_sql:
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

        return {
            "db_result": formatted_rows,
            "sql_error": "",
            "table_columns": columns,
            "row_count": row_count,
            "truncated": truncated,
        }
    except Exception as exc:
        logger.error("SQL Execution Error: %s", exc)
        return {
            "db_result": [],
            "sql_error": str(exc),
            "table_columns": [],
            "row_count": None,
            "truncated": False,
        }
