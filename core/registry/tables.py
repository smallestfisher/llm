from __future__ import annotations

from core.config.loader import load_tables


DOMAIN_TABLES = {
    "production": [
        "production_actuals",
        "daily_schedule",
        "weekly_rolling_plan",
        "monthly_plan_approved",
        "p_demand",
        "v_demand",
        "sales_financial_perf",
        "work_in_progress",
        "product_attributes",
        "product_mapping",
    ],
    "inventory": [
        "daily_inventory",
        "oms_inventory",
        "work_in_progress",
        "daily_schedule",
        "product_attributes",
        "product_mapping",
    ],
}


def get_tables_for_domain(domain: str) -> list[str]:
    return list(DOMAIN_TABLES.get(domain, []))


def explicit_table_hits(question: str) -> list[str]:
    q = question.lower()
    hits: list[str] = []
    for table_name in load_tables().keys():
        if table_name.lower() in q and table_name not in hits:
            hits.append(table_name)
    return hits


def build_schema_excerpt(table_names: list[str]) -> str:
    tables = load_tables()
    lines: list[str] = []
    for table_name in table_names:
        info = tables.get(table_name)
        if not info:
            continue
        lines.append(f"Table: {table_name}")
        description = info.get("description")
        if description:
            lines.append(f"Description: {description}")
        columns = info.get("columns") or []
        if columns:
            lines.append("Columns: " + ", ".join(columns))
        relationships = info.get("relationships") or {}
        if relationships:
            lines.append("Relationships:")
            for column_name, target in relationships.items():
                lines.append(f"- {column_name} -> {target}")
        lines.append("")
    return "\n".join(lines).strip()
