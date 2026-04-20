from __future__ import annotations

import json
import re
from typing import Any

from app.semantic.schema_registry import load_tables
from app.execution.query_constraints import resolve_query_shape_constraints


_TABLES = load_tables()


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
        lambda match: "" if _is_suspicious_literal(match.group("value")) else match.group(0),
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
    query_state: dict[str, Any] | None = None,
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

    shape = resolve_query_shape_constraints(query_state, allowed_tables)
    required_columns = list(shape.get("required_columns") or [])
    if required_columns:
        missing = [column for column in required_columns if not _sql_mentions_any(normalized_sql, (column,))]
        if missing:
            issues.append(f"SQL 缺少查询状态要求的字段: {', '.join(missing)}")

    require_aggregate = bool(shape.get("require_aggregate"))
    forbid_aggregate = bool(shape.get("forbid_aggregate"))
    require_group_by_columns = list(shape.get("require_group_by_columns") or [])
    has_aggregate = any(token in lower_sql for token in ("count(", "sum(", "avg(", "min(", "max("))
    has_group_by = " group by " in f" {lower_sql} "
    if require_aggregate and not (has_aggregate or has_group_by):
        issues.append("当前查询状态要求 summary 结果，SQL 必须包含聚合或分组")
    if forbid_aggregate and has_aggregate:
        issues.append("当前查询状态要求 detail 结果，SQL 不应包含聚合函数")
    if require_group_by_columns and has_group_by:
        missing_group_by = [column for column in require_group_by_columns if not re.search(rf"(?is)group\s+by[^;]*\b{re.escape(column)}\b", normalized_sql)]
        if missing_group_by:
            issues.append(f"GROUP BY 缺少查询状态要求的维度字段: {', '.join(missing_group_by)}")

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
    query_state: dict[str, Any] | None = None,
) -> str:
    hardened = (sql or "").strip()
    if not hardened:
        return hardened

    filters = dict(structured_filters or {})
    lower_sql = hardened.lower()

    month_token_map = {
        "CURRENT_MONTH": "DATE_FORMAT(CURDATE(), '%Y-%m')",
        "PREVIOUS_MONTH": "DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m')",
        "LAST_MONTH": "DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m')",
        "NEXT_MONTH": "DATE_FORMAT(DATE_ADD(CURDATE(), INTERVAL 1 MONTH), '%Y-%m')",
    }
    for token, replacement in month_token_map.items():
        hardened = re.sub(rf"\b{token}\b", replacement, hardened, flags=re.IGNORECASE)

    relative_month = filters.get("relative_month")
    if relative_month and any(column in lower_sql for column in ("plan_month", "report_month", " month ")):
        relative_month_sql = {
            "current_month": "DATE_FORMAT(CURDATE(), '%Y-%m')",
            "previous_month": "DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m')",
            "next_month": "DATE_FORMAT(DATE_ADD(CURDATE(), INTERVAL 1 MONTH), '%Y-%m')",
        }.get(relative_month)
        if relative_month_sql:
            hardened = re.sub(r"\bCURRENT_MONTH\b", relative_month_sql, hardened, flags=re.IGNORECASE)

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
