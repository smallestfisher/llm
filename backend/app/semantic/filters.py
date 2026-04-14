from __future__ import annotations

import re
from typing import Any

from app.semantic.heuristics import (
    extract_recent_days,
    guess_single_table,
    has_explicit_date,
    refine_simple_filters,
)


_DATE_RANGE = re.compile(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})")
_MONTH_RANGE = re.compile(r"(\d{4}[-/]\d{1,2})")
_VERSION_RANGE = re.compile(r"(20\d{2}W\d{2})", re.IGNORECASE)
_FACTORY_RANGE = re.compile(r"\b(B\d+_[A-Z]{2}|BJ\d{2}|CD\d{2}|MY\d{2}|WH\d{2})\b")


def extract_shared_filters(question: str) -> dict[str, Any]:
    q = (question or "").strip()
    filters: dict[str, Any] = {}

    recent_days = extract_recent_days(q)
    if recent_days and not has_explicit_date(q):
        filters["recent_days"] = recent_days

    if any(token in q for token in ("最新", "最近一期", "最新一期")):
        filters["latest"] = True

    if "今天" in q:
        filters["relative_day"] = "today"
    elif "昨天" in q:
        filters["relative_day"] = "yesterday"

    if any(token in q for token in ("这个月", "本月", "当月")):
        filters["relative_month"] = "current_month"
    elif any(token in q for token in ("上个月", "上月")):
        filters["relative_month"] = "previous_month"
    elif any(token in q for token in ("下个月", "下月")):
        filters["relative_month"] = "next_month"

    if any(token in q for token in ("这周", "本周")):
        filters["relative_week"] = "current_week"
    elif any(token in q for token in ("上周", "上一周")):
        filters["relative_week"] = "previous_week"
    elif any(token in q for token in ("下周", "下一周")):
        filters["relative_week"] = "next_week"

    version_match = _VERSION_RANGE.search(q)
    if version_match:
        filters["PM_VERSION"] = version_match.group(1).upper()

    factory_match = _FACTORY_RANGE.search(q)
    if factory_match:
        filters["factory"] = factory_match.group(1).upper()

    dates = _DATE_RANGE.findall(q)
    if len(dates) >= 2:
        filters["date_from"] = dates[0].replace("/", "-")
        filters["date_to"] = dates[1].replace("/", "-")
    elif len(dates) == 1:
        filters["date_from"] = dates[0].replace("/", "-")

    months = _MONTH_RANGE.findall(q)
    if "date_from" not in filters and months:
        if len(months) >= 2:
            filters["month_from"] = months[0].replace("/", "-")
            filters["month_to"] = months[1].replace("/", "-")
        else:
            filters["month"] = months[0].replace("/", "-")

    return filters


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
