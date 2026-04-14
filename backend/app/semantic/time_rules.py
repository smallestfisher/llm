from __future__ import annotations

import re


RECENT_DAYS_PATTERN = re.compile(r"(最近|近)\s*(\d+)\s*天")
DATE_PATTERN = re.compile(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b")
MONTH_PATTERN = re.compile(r"\b\d{4}[-/]\d{1,2}\b")


def extract_recent_days(question: str) -> int:
    m = RECENT_DAYS_PATTERN.search(question)
    if not m:
        if "最近一周" in question or "近一周" in question:
            return 7
        return 0
    return int(m.group(2))


def has_explicit_date(question: str) -> bool:
    return DATE_PATTERN.search(question) is not None or MONTH_PATTERN.search(question) is not None
