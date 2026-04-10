from __future__ import annotations

import re
from typing import Any

from core.heuristics import extract_recent_days, has_explicit_date


_DATE_RANGE = re.compile(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})")
_MONTH_RANGE = re.compile(r"(\d{4}[-/]\d{1,2})")


def extract_shared_filters(question: str) -> dict[str, Any]:
    q = (question or "").strip()
    filters: dict[str, Any] = {}

    recent_days = extract_recent_days(q)
    if recent_days and not has_explicit_date(q):
        filters["recent_days"] = recent_days

    if any(token in q for token in ("最新", "最近一期", "最新一期")):
        filters["latest"] = True

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
