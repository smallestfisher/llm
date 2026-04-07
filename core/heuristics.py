import re
from difflib import SequenceMatcher
from typing import Dict, Any, List

from core.config.loader import load_heuristics, load_tables


_TABLE_NAMES = list(load_tables().keys())

_heur = load_heuristics()
_GROUP_BY_KEYWORDS = list(_heur.get("group_by_keywords", {}).items())
_METRIC_KEYWORDS = [
    (k, v[0], v[1]) for k, v in _heur.get("metric_keywords", {}).items()
]
_COUNT_KEYWORDS = _heur.get("count_keywords", [])

_RECENT_DAYS_PATTERN = re.compile(r"(最近|近)\s*(\d+)\s*天")
_DATE_PATTERN = re.compile(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b")
_MONTH_PATTERN = re.compile(r"\b\d{4}[-/]\d{1,2}\b")

_MULTI_TABLE_KEYWORDS = ["对比", "匹配", "联合", "关联", "结合", "同时", "vs", "VS", "对照", "联表"]


def _find_table(question: str) -> str:
    for t in _TABLE_NAMES:
        if f"({t})" in question or re.search(rf"\b{t}\b", question):
            return t
    return ""


def guess_single_table(question: str) -> str:
    table = _find_table(question)
    if not table:
        return ""
    if any(k in question for k in _MULTI_TABLE_KEYWORDS):
        return ""
    return table


def refine_simple_filters(question: str, filters: Dict[str, Any]) -> Dict[str, Any]:
    q = question
    out = dict(filters or {})

    # table
    if not out.get("table"):
        table = _find_table(q)
        if table:
            out["table"] = table

    table = out.get("table")
    tables = load_tables()
    if not table or table not in tables:
        return out

    columns = set(tables[table]["columns"])

    # group_by
    if not out.get("group_by"):
        gb: List[str] = []
        for kw, field in _GROUP_BY_KEYWORDS:
            if kw in q and field in columns:
                gb.append(field)
        if gb:
            out["group_by"] = gb

    def _norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", s.lower())

    def _fuzzy_match_column(field: str) -> str:
        if not field:
            return ""
        f = _norm(field)
        best = ("", 0.0)
        for col in columns:
            score = SequenceMatcher(None, f, _norm(col)).ratio()
            if score > best[1]:
                best = (col, score)
        return best[0] if best[1] >= 0.78 else ""

    # group_by: validate and repair invalid fields
    if out.get("group_by"):
        repaired = []
        for g in out["group_by"]:
            if g in columns:
                repaired.append(g)
            else:
                m = _fuzzy_match_column(str(g))
                if m:
                    repaired.append(m)
        out["group_by"] = repaired

    # metric: validate and repair invalid field
    if out.get("metric_field") and out.get("metric_field") not in columns:
        m = _fuzzy_match_column(str(out.get("metric_field")))
        if m:
            out["metric_field"] = m
        else:
            out.pop("metric_field", None)
            out.pop("metric", None)

    if not out.get("metric") or not out.get("metric_field"):
        for kw, field, metric in _METRIC_KEYWORDS:
            if kw in q and field in columns:
                out["metric"] = metric
                out["metric_field"] = field
                break

    if not out.get("metric"):
        if any(k in q for k in _COUNT_KEYWORDS):
            out["metric"] = "count"

    # recent days
    if "date_from" not in out and "date_to" not in out:
        m = _RECENT_DAYS_PATTERN.search(q)
        if m:
            out["recent_days"] = int(m.group(2))
        elif "最近一周" in q or "近一周" in q:
            out["recent_days"] = 7

    return out


def extract_recent_days(question: str) -> int:
    m = _RECENT_DAYS_PATTERN.search(question)
    if not m:
        if "最近一周" in question or "近一周" in question:
            return 7
        return 0
    return int(m.group(2))


def has_explicit_date(question: str) -> bool:
    return _DATE_PATTERN.search(question) is not None or _MONTH_PATTERN.search(question) is not None
