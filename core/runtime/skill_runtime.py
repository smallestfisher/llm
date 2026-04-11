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

from core.config.loader import load_tables
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
_TABLES = load_tables()


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


def _raw_column_name(column: str) -> str:
    return column.split(" (", 1)[0].strip()


def _expand_select_star(
    sql: str,
    *,
    question: str,
    structured_filters: dict[str, Any],
    allowed_tables: list[str] | None,
) -> str:
    match = re.match(
        r"(?is)^\s*select\s+\*\s+from\s+([a-zA-Z_][\w]*)\s*(?:([a-zA-Z_][\w]*)\s*)?(.*)$",
        sql.strip(),
    )
    if not match:
        return sql

    table_name = match.group(1)
    maybe_alias = match.group(2) or ""
    suffix = (match.group(3) or "").strip()
    if table_name not in _TABLES:
        return sql
    if allowed_tables and table_name not in allowed_tables:
        return sql
    if any(token in question for token in ("全部字段", "所有字段", "完整记录", "原始记录")):
        return sql

    alias = ""
    if maybe_alias and maybe_alias.upper() not in {
        "WHERE",
        "GROUP",
        "ORDER",
        "LIMIT",
        "HAVING",
        "JOIN",
        "LEFT",
        "RIGHT",
        "INNER",
        "OUTER",
        "UNION",
    }:
        alias = maybe_alias
    elif maybe_alias:
        suffix = f"{maybe_alias} {suffix}".strip()

    columns = [_raw_column_name(col) for col in (_TABLES[table_name].get("columns") or [])]
    if not columns:
        return sql

    projected = ", ".join(f"{alias}.{col}" if alias else col for col in columns)
    alias_sql = f" {alias}" if alias else ""
    suffix_sql = f" {suffix}" if suffix else ""
    return f"SELECT {projected} FROM {table_name}{alias_sql}{suffix_sql}".strip()


def _strip_inventory_threshold_having(sql: str, *, question: str, domain: str) -> str:
    if domain != "inventory":
        return sql
    if re.search(r"\d", question):
        return sql
    return re.sub(
        r"(?is)\s+having\s+[^;]*?(?:total_ttl_qty|total_hold_qty)[^;]*$",
        "",
        sql.strip(),
    )


def _is_suspicious_literal(value: str) -> bool:
    return bool(
        re.match(
            r"(?is)^(your_.+|example.*|sample.*|FACTORY\d+|PRODUCT\d+|ERP_FACTORY_[A-Z0-9_]+|ERP_LOCATION_[A-Z0-9_]+|CHECKIN_[A-Z0-9_]+|TYPE_[A-Z0-9_]+|GRADE_[A-Z0-9_]+)$",
            value.strip(),
        )
    )


def _strip_suspicious_literal_filters(sql: str) -> str:
    hardened = sql
    fields = (
        "factory_code",
        "FACTORY",
        "factory",
        "ERP_FACTORY",
        "ERP_LOCATION",
        "product_ID",
        "FGCODE",
        "PRODUCTION_TYPE",
        "GRADE",
        "CHECKINCODE",
        "CUSTOMER",
    )
    field_pattern = "|".join(re.escape(field) for field in fields)

    def replace_where(match: re.Match) -> str:
        value = match.group("value")
        return "WHERE " if _is_suspicious_literal(value) else match.group(0)

    def replace_and(match: re.Match) -> str:
        value = match.group("value")
        return "" if _is_suspicious_literal(value) else match.group(0)

    hardened = re.sub(
        rf"(?is)\bWHERE\s+(?P<field>{field_pattern})\s*=\s*'(?P<value>[^']+)'\s+AND\s+",
        replace_where,
        hardened,
    )
    hardened = re.sub(
        rf"(?is)\s+AND\s+(?P<field>{field_pattern})\s*=\s*'(?P<value>[^']+)'",
        replace_and,
        hardened,
    )
    hardened = re.sub(
        rf"(?is)\bWHERE\s+(?P<field>{field_pattern})\s*=\s*'(?P<value>[^']+)'\s*$",
        lambda match: "" if _is_suspicious_literal(match.group('value')) else match.group(0),
        hardened,
    )
    hardened = re.sub(r"(?is)\bWHERE\s+(GROUP BY|ORDER BY|LIMIT|HAVING)\b", r"\1", hardened)
    hardened = re.sub(r"\s{2,}", " ", hardened).strip()
    return hardened


def _quote_spaced_columns(sql: str) -> str:
    hardened = sql
    spaced_columns = ("Cell No", "Array No", "CF No")
    for column in spaced_columns:
        pattern = rf"(?<!`)\b{re.escape(column)}\b(?!`)"
        hardened = re.sub(pattern, f"`{column}`", hardened)
    return hardened


def _question_requests_full_detail(question: str) -> bool:
    return any(token in question for token in ("全部字段", "所有字段", "完整记录", "原始记录", "全量明细"))


def _sql_mentions_any(sql: str, tokens: tuple[str, ...] | list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(token)}\b", sql, re.IGNORECASE) for token in tokens if token)


def lint_sql(
    sql: str,
    *,
    question: str = "",
    domain: str = "",
    structured_filters: dict[str, Any] | None = None,
    allowed_tables: list[str] | None = None,
) -> list[str]:
    issues: list[str] = []
    normalized_sql = (sql or "").strip()
    if not normalized_sql:
        return ["SQL 为空"]

    filters = dict(structured_filters or {})
    lower_sql = normalized_sql.lower()

    if re.search(r"(?is)\bselect\s+\*", normalized_sql) and not _question_requests_full_detail(question):
        issues.append("不要使用 SELECT *，请显式列出需要的字段")

    if filters.get("PM_VERSION"):
        version_value = str(filters["PM_VERSION"])
        has_version_filter = bool(
            re.search(r"(?is)\bPM_VERSION\s*=\s*", normalized_sql)
            or version_value in normalized_sql
        )
        if not has_version_filter:
            issues.append(f"缺少版本过滤条件 {version_value}")

    if filters.get("factory") and not _sql_mentions_any(normalized_sql, ("factory_code", "FACTORY", "factory", str(filters["factory"]))):
        issues.append(f"缺少工厂过滤条件 {filters['factory']}")

    has_time_filter = any(
        key in filters
        for key in ("date_from", "date_to", "month", "month_from", "month_to", "recent_days", "relative_day", "relative_week", "relative_month")
    )
    if has_time_filter and " where " not in f" {lower_sql} ":
        issues.append("问题包含时间条件，但 SQL 缺少 WHERE 过滤")

    if domain in {"sales", "planning"}:
        has_helper_join = _sql_mentions_any(normalized_sql, ("join product_attributes", "join product_mapping"))
        productish_question = any(token in question for token in ("产品", "料号", "FGCODE", "product", "application", "分类", "CUT"))
        if has_helper_join and not productish_question:
            issues.append("当前问题不需要维表补充，避免无意义 JOIN product_attributes/product_mapping")

    if domain == "inventory" and re.search(r"(?is)\bhaving\b[^;]*\b\d+\b", normalized_sql) and not re.search(r"\d", question):
        issues.append("库存问题出现了未由用户指定的固定阈值 HAVING 条件")

    if re.search(r"(?is)'(?:your_[^']+|example[^']*|sample[^']*)'", normalized_sql):
        issues.append("SQL 包含占位或示例字面值，请改为真实过滤条件或删除该条件")

    if allowed_tables:
        referenced_tables = set(
            match.group(1)
            for match in re.finditer(r"(?is)\b(?:from|join)\s+([a-zA-Z_][\w]*)\b", normalized_sql)
        )
        unexpected_tables = sorted(table for table in referenced_tables if table not in allowed_tables)
        if unexpected_tables:
            issues.append(f"SQL 使用了越界表: {', '.join(unexpected_tables)}")

    return issues


def harden_sql(
    sql: str,
    structured_filters: dict[str, Any] | None = None,
    *,
    question: str = "",
    domain: str = "",
    allowed_tables: list[str] | None = None,
) -> str:
    hardened = (sql or "").strip()
    if not hardened:
        return hardened

    filters = dict(structured_filters or {})
    lower_sql = hardened.lower()

    # Normalize common LLM placeholders into valid MySQL month expressions.
    month_token_map = {
        "CURRENT_MONTH": "DATE_FORMAT(CURDATE(), '%Y-%m')",
        "PREVIOUS_MONTH": "DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m')",
        "LAST_MONTH": "DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m')",
        "NEXT_MONTH": "DATE_FORMAT(DATE_ADD(CURDATE(), INTERVAL 1 MONTH), '%Y-%m')",
    }
    for token, replacement in month_token_map.items():
        hardened = re.sub(rf"\b{token}\b", replacement, hardened, flags=re.IGNORECASE)

    # Align relative-month filters to common month columns when the model emits placeholders.
    relative_month = filters.get("relative_month")
    if relative_month and any(column in lower_sql for column in ("plan_month", "report_month", " month ")):
        relative_month_sql = {
            "current_month": "DATE_FORMAT(CURDATE(), '%Y-%m')",
            "previous_month": "DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m')",
            "next_month": "DATE_FORMAT(DATE_ADD(CURDATE(), INTERVAL 1 MONTH), '%Y-%m')",
        }.get(relative_month)
        if relative_month_sql:
            hardened = re.sub(r"\bCURRENT_MONTH\b", relative_month_sql, hardened, flags=re.IGNORECASE)

    # Normalize common synthetic demand month aliases into real horizontal columns.
    if any(table in lower_sql for table in ("p_demand", "v_demand")):
        demand_alias_map = {
            "MONTH2": "NEXT_REQUIREMENT",
            "MONTH_2": "NEXT_REQUIREMENT",
            "SECOND_MONTH": "NEXT_REQUIREMENT",
            "MONTH3": "LAST_REQUIREMENT",
            "MONTH_3": "LAST_REQUIREMENT",
            "THIRD_MONTH": "LAST_REQUIREMENT",
        }
        for token, replacement in demand_alias_map.items():
            hardened = re.sub(rf"\b{token}\b", replacement, hardened, flags=re.IGNORECASE)

    hardened = _expand_select_star(
        hardened,
        question=question,
        structured_filters=filters,
        allowed_tables=allowed_tables,
    )
    hardened = _strip_inventory_threshold_having(hardened, question=question, domain=domain)
    hardened = _strip_suspicious_literal_filters(hardened)
    hardened = _quote_spaced_columns(hardened)

    return hardened


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
