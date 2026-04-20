from __future__ import annotations

from typing import Any

from app.semantic.schema_registry import load_tables

_TABLES = load_tables()

_DIMENSION_COLUMN_CANDIDATES = {
    "version": ["PM_VERSION"],
    "factory": ["factory_code", "FACTORY", "factory", "ERP_FACTORY"],
    "customer": ["CUSTOMER"],
    "product": ["product_ID", "FGCODE"],
}

_DETAIL_LEVELS = {"detail", "summary"}


def resolve_required_columns(query_state: dict[str, Any] | None, allowed_tables: list[str] | None = None) -> list[str]:
    state = dict(query_state or {})
    requested = list(state.get("dimensions") or [])
    requested += list((state.get("presentation") or {}).get("show_fields") or [])
    resolved: list[str] = []
    tables = allowed_tables or list(_TABLES.keys())
    for token in requested:
        token_text = str(token).strip()
        if not token_text:
            continue
        direct = _resolve_direct_column(token_text, tables)
        if direct and direct not in resolved:
            resolved.append(direct)
            continue
        for candidate in _DIMENSION_COLUMN_CANDIDATES.get(token_text, []):
            if _column_available(candidate, tables) and candidate not in resolved:
                resolved.append(candidate)
    return resolved


def resolve_query_shape_constraints(query_state: dict[str, Any] | None, allowed_tables: list[str] | None = None) -> dict[str, Any]:
    state = dict(query_state or {})
    presentation = dict(state.get("presentation") or {})
    detail_level = str(presentation.get("detail_level") or "").strip().lower()
    if detail_level not in _DETAIL_LEVELS:
        detail_level = ""

    required_columns = resolve_required_columns(state, allowed_tables)
    dimensions = list(state.get("dimensions") or [])
    grouped_columns: list[str] = []
    tables = allowed_tables or list(_TABLES.keys())
    for token in dimensions:
        token_text = str(token).strip()
        direct = _resolve_direct_column(token_text, tables)
        if direct and direct not in grouped_columns:
            grouped_columns.append(direct)
            continue
        for candidate in _DIMENSION_COLUMN_CANDIDATES.get(token_text, []):
            if _column_available(candidate, tables) and candidate not in grouped_columns:
                grouped_columns.append(candidate)

    require_aggregate = detail_level == "summary"
    forbid_aggregate = detail_level == "detail"
    require_group_by_columns = grouped_columns if grouped_columns and not forbid_aggregate else []

    return {
        "required_columns": required_columns,
        "detail_level": detail_level,
        "require_aggregate": require_aggregate,
        "forbid_aggregate": forbid_aggregate,
        "require_group_by_columns": require_group_by_columns,
    }


def format_query_constraints_text(constraints: dict[str, Any] | None) -> str:
    data = dict(constraints or {})
    lines: list[str] = []
    required_columns = [str(col).strip() for col in data.get("required_columns") or [] if str(col).strip()]
    if required_columns:
        lines.append(f"必须在 SELECT 中包含字段: {', '.join(required_columns)}")

    required_group_by = [str(col).strip() for col in data.get("require_group_by_columns") or [] if str(col).strip()]
    if required_group_by:
        lines.append(f"若使用聚合，GROUP BY 必须覆盖字段: {', '.join(required_group_by)}")

    if data.get("require_aggregate"):
        lines.append("当前是 summary 形态，SQL 必须包含聚合函数或分组统计。")
    if data.get("forbid_aggregate"):
        lines.append("当前是 detail 形态，SQL 不应包含聚合函数。")

    return "\n".join(f"- {row}" for row in lines) if lines else "- 无额外结构约束"


def _resolve_direct_column(token: str, tables: list[str]) -> str:
    token_upper = token.strip().strip("`").split(".")[-1].upper()
    for table_name in tables:
        table = _TABLES.get(table_name) or {}
        for raw in table.get("columns") or []:
            column = raw.split(" (", 1)[0].strip()
            if column.upper() == token_upper:
                return column
    return ""


def _column_available(column: str, tables: list[str]) -> bool:
    for table_name in tables:
        table = _TABLES.get(table_name) or {}
        columns = [raw.split(" (", 1)[0].strip() for raw in (table.get("columns") or [])]
        if column in columns:
            return True
    return False
