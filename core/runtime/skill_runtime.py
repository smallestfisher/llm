from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

try:
    import pandas as pd
except Exception:
    pd = None

from openai import OpenAI

from core.database import get_db_connection
from core.heuristics import extract_recent_days, guess_single_table, has_explicit_date, refine_simple_filters


logger = logging.getLogger("boe.runtime")
DEBUG_TRACE = os.getenv("DEBUG_TRACE", "0") == "1"
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen3-14B")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-no-key")
MAX_TABLE_ROWS = int(os.getenv("MAX_TABLE_ROWS", "200"))
SAMPLE_LIMIT = int(os.getenv("SAMPLE_LIMIT", "5000"))
AUTO_TRUNCATE_ROWS = int(os.getenv("AUTO_TRUNCATE_ROWS", "50000"))

_openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
_db = get_db_connection()


def llm_complete(prompt: str, stream: bool = False) -> str:
    response = _openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=LLM_TEMPERATURE,
        stream=stream,
    )
    if not stream:
        return (response.choices[0].message.content or "").strip()

    full_text = ""
    reasoning_started = False
    content_started = False

    def _extract_stream_text(delta, attr_name: str) -> str:
        value = getattr(delta, attr_name, None)
        if not value:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("content") or ""))
                else:
                    parts.append(str(getattr(item, "text", "") or getattr(item, "content", "") or ""))
            return "".join(parts)
        if isinstance(value, dict):
            return str(value.get("text") or value.get("content") or "")
        return str(getattr(value, "text", "") or getattr(value, "content", "") or "")

    for chunk in response:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue
        delta = getattr(choices[0], "delta", None)
        if not delta:
            continue

        reasoning_text = ""
        for field_name in ("reasoning_content", "reasoning", "reasoning_text"):
            reasoning_text = _extract_stream_text(delta, field_name)
            if reasoning_text:
                break

        if DEBUG_TRACE and reasoning_text:
            if not reasoning_started:
                print("\n[REASONING]: ", end="", flush=True)
                reasoning_started = True
            print(reasoning_text, end="", flush=True)

        content_text = _extract_stream_text(delta, "content")
        if content_text:
            if DEBUG_TRACE and reasoning_started and not content_started:
                print("\n[CONTENT]: ", end="", flush=True)
            elif not DEBUG_TRACE and not content_started:
                print("\n[STREAMING]: ", end="", flush=True)
            content_started = True
            print(content_text, end="", flush=True)
            full_text += content_text

    if DEBUG_TRACE and reasoning_started:
        print("", flush=True)
    if content_started:
        print("\n", flush=True)
    return full_text.strip()


def sanitize_sql(text: str) -> str:
    sql = (text or "").strip()
    if sql.startswith("```sql"):
        sql = sql[6:]
    if sql.startswith("```"):
        sql = sql[3:]
    if sql.endswith("```"):
        sql = sql[:-3]
    sql = sql.strip()
    if ";" in sql:
        sql = sql.split(";", 1)[0].strip()
    return sql


def safe_json_loads(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except Exception:
                return {}
        return {}


def apply_filter_refinement(
    *,
    question: str,
    intent: str,
    filters: dict[str, Any],
    allowed_tables: list[str] | None = None,
) -> dict[str, Any]:
    refined_filters = dict(filters or {})
    recent_days = extract_recent_days(question)
    if recent_days and not has_explicit_date(question):
        refined_filters.pop("date_from", None)
        refined_filters.pop("date_to", None)
        refined_filters["recent_days"] = recent_days

    single_table = guess_single_table(question)
    if single_table:
        refined_filters["table"] = single_table

    if allowed_tables and refined_filters.get("table") not in allowed_tables:
        refined_filters.pop("table", None)

    if intent == "simple_table_query" or single_table:
        refined_filters = refine_simple_filters(question, refined_filters)

    if allowed_tables and refined_filters.get("table") not in allowed_tables:
        refined_filters.pop("table", None)

    return refined_filters


def execute_sql(sql: str) -> dict[str, Any]:
    if not sql:
        return {"db_result": [], "sql_error": "SQL 为空", "table_columns": [], "row_count": None, "truncated": False}

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


def build_answer_payload(
    *,
    question: str,
    sql_query: str,
    sql_error: str,
    db_result: list[Any],
    columns: list[str],
    row_count: int | None,
    truncated: bool,
    answer_prompt: str,
) -> dict[str, Any]:
    if sql_error:
        answer = f"⚠️ 数据库查询出错：\n{sql_error}"
        return {
            "final_answer": answer,
            "chart_data": None,
            "table_data": [],
            "table_columns": columns,
            "row_count": row_count,
            "truncated": truncated,
            "chat_history": [f"问: {question}\n答: {answer}"],
        }

    if pd is None:
        df = None
        db_preview = json.dumps(db_result[:20], ensure_ascii=False)
        table_data = db_result[:MAX_TABLE_ROWS]
        summary_text = f"查询结果共 {row_count or len(db_result)} 条记录。" if db_result else "未查询到数据。"
        is_aggregate = any(token in sql_query.lower() for token in (" group by ", "count(", "sum(", "avg(", "min(", "max("))
    else:
        if db_result and columns:
            df = pd.DataFrame(db_result, columns=columns)
        elif db_result:
            df = pd.DataFrame(db_result)
        else:
            df = pd.DataFrame()

        lower_sql = sql_query.lower()
        is_aggregate = (" group by " in lower_sql) or any(
            token in lower_sql for token in ("count(", "sum(", "avg(", "min(", "max(")
        )

        if not df.empty:
            total_count = row_count or len(df)
            summary_text = f"查询结果共 {total_count} 条记录。"
            numeric_cols = df.select_dtypes(include=["number"]).columns
            if len(numeric_cols) > 0:
                summary_text += f" 关键指标汇总: {df[numeric_cols].sum().to_dict()}"
            db_preview = df.head(20).to_json(orient="records", force_ascii=False)
            for col in df.select_dtypes(include=["object"]).columns:
                if any(isinstance(val, Decimal) for val in df[col]):
                    df[col] = df[col].astype(float)
            table_data = df.head(MAX_TABLE_ROWS).to_dict(orient="records")
        else:
            db_preview = "[]"
            table_data = []
            summary_text = "未查询到数据。"

    if db_result and not is_aggregate:
        if truncated and row_count:
            answer = f"已查询到 {row_count} 条记录，当前展示前 {len(db_result)} 条。结果集较大，请结合筛选条件缩小范围后继续查看。"
        else:
            answer = f"已查询到 {row_count or len(db_result)} 条记录，请查看下方结果表。"
        return {
            "final_answer": answer,
            "chart_data": None,
            "table_data": table_data,
            "table_columns": columns,
            "row_count": row_count,
            "truncated": truncated,
            "chat_history": [f"问: {question}\n答: {answer}"],
        }

    answer = llm_complete(answer_prompt.format(question=question, sql_query=sql_query, db_result=db_preview, data_summary=summary_text))
    return {
        "final_answer": answer,
        "chart_data": None,
        "table_data": table_data,
        "table_columns": columns,
        "row_count": row_count,
        "truncated": truncated,
        "chat_history": [f"问: {question}\n答: {answer}"],
    }
