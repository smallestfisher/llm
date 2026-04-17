from __future__ import annotations

import re
from datetime import date, timedelta
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
_DEMAND_VERSION_EXACT = re.compile(r"\b(20\d{2}\d{2}W[1-5][PV]\d+)\b", re.IGNORECASE)
_DEMAND_WEEK_PREFIX = re.compile(r"\b(20\d{2}\d{2}W[1-5])(?:[PV]\d+)?\b", re.IGNORECASE)
_YEAR_MONTH_WEEK = re.compile(r"(20\d{2})[年/-]?(\d{1,2})月?(?:第)?([1-5一二三四五])(?:周|w)", re.IGNORECASE)
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


def _week_of_month(target: date) -> int:
    return min(5, max(1, ((target.day - 1) // 7) + 1))


def _infer_demand_table_type(question: str, allowed_tables: list[str] | None = None) -> str:
    q = (question or "").lower()
    allowed = set(allowed_tables or [])
    if "p_demand" in allowed and "v_demand" not in allowed:
        return "P"
    if "v_demand" in allowed and "p_demand" not in allowed:
        return "V"
    if any(token in q for token in ("p版", "commit", "承诺", "承诺需求")):
        return "P"
    if any(token in q for token in ("v版", "forecast", "预测需求", "原始需求", "客户需求")):
        return "V"
    return ""


def _resolve_relative_week_prefix(relative_week: str) -> str:
    base = date.today()
    offset_days = {
        "previous_week": -7,
        "current_week": 0,
        "next_week": 7,
    }.get(relative_week, 0)
    target = base + timedelta(days=offset_days)
    return f"{target.year}{target.month:02d}W{_week_of_month(target)}"


def _build_demand_version_filters(
    question: str,
    filters: dict[str, Any],
    *,
    allowed_tables: list[str] | None = None,
) -> dict[str, Any]:
    allowed = set(allowed_tables or [])
    if allowed and "p_demand" not in allowed and "v_demand" not in allowed:
        return {}

    q = (question or "").strip()
    exact_match = _DEMAND_VERSION_EXACT.search(q)
    if exact_match:
        exact = exact_match.group(1).upper()
        table_type = "P" if "P" in exact else "V" if "V" in exact else ""
        return {
            "pm_version_exact": exact,
            "pm_version_prefix": exact.split(table_type, 1)[0] if table_type else exact,
            "pm_version_table_type": table_type,
        }

    prefix_match = _DEMAND_WEEK_PREFIX.search(q)
    if prefix_match:
        return {
            "pm_version_prefix": prefix_match.group(1).upper(),
            "pm_version_table_type": _infer_demand_table_type(q, allowed_tables),
        }

    ymw_match = _YEAR_MONTH_WEEK.search(q)
    if ymw_match:
        year = int(ymw_match.group(1))
        month = int(ymw_match.group(2))
        week_token = ymw_match.group(3)
        if week_token in {"一", "二", "三", "四", "五"}:
            week = {
                "一": 1,
                "二": 2,
                "三": 3,
                "四": 4,
                "五": 5,
            }[week_token]
        else:
            week = int(week_token)
        if 1 <= month <= 12:
            return {
                "pm_version_prefix": f"{year}{month:02d}W{week}",
                "pm_version_table_type": _infer_demand_table_type(q, allowed_tables),
            }

    relative_week = str(filters.get("relative_week") or "")
    if relative_week:
        return {
            "pm_version_prefix": _resolve_relative_week_prefix(relative_week),
            "pm_version_table_type": _infer_demand_table_type(q, allowed_tables),
        }

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

    demand_filters = _build_demand_version_filters(
        question,
        refined_filters,
        allowed_tables=allowed_tables,
    )
    if demand_filters:
        refined_filters.update({key: value for key, value in demand_filters.items() if value})

    if allowed_tables and refined_filters.get("table") not in allowed_tables:
        refined_filters.pop("table", None)

    return refined_filters
