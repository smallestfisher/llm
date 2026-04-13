from __future__ import annotations

import json

from core.router.filter_extractor import extract_shared_filters
from core.registry.tables import explicit_table_hits, get_tables_for_domain
from core.runtime.skill_runtime import llm_complete
from core.runtime.state import RouteDecision
from core.skills.prompting import build_route_decision_prompt


_DOMAIN_KEYWORDS = {
    "production": {
        "生产": 2.0,
        "实绩": 2.4,
        "产出": 2.4,
        "投入": 2.4,
        "报废": 2.6,
        "产线": 1.8,
        "线别": 1.6,
        "不良": 2.6,
        "投料": 1.5,
        "实际": 1.6,
        "风险": 0.4,
    },
    "planning": {
        "排产": 2.6,
        "计划": 1.8,
        "日计划": 2.0,
        "日排产": 2.0,
        "月计划": 2.2,
        "周计划": 2.2,
        "周滚": 2.0,
        "滚动计划": 2.0,
        "版本": 1.8,
        "审批版": 1.8,
        "锁版": 1.8,
        "计划兑现": 1.5,
        "计划偏差": 1.5,
    },
    "inventory": {
        "库存": 2.4,
        "在途": 2.0,
        "hub": 2.0,
        "缺货": 2.0,
        "齐套": 2.0,
        "支撑": 1.0,
        "覆盖": 1.0,
        "仓库": 1.8,
        "仓": 1.2,
        "备货": 1.4,
        "客户仓": 2.0,
        "库存覆盖": 2.0,
        "oms": 2.2,
        "ttl": 1.8,
        "hold": 1.8,
        "期初": 1.8,
        "库龄": 2.0,
        "库位": 1.4,
        "erp": 1.2,
        "风险": 0.4,
        "缺料": 2.0,
    },
    "demand": {
        "需求": 2.2,
        "forecast": 2.6,
        "commit": 2.6,
        "承诺": 2.2,
        "承诺需求": 2.2,
        "客户需求": 2.2,
        "覆盖": 1.6,
        "缺口": 1.6,
        "v版": 2.6,
        "p版": 2.6,
        "版本": 1.2,
    },
    "sales": {
        "销售": 2.6,
        "销售量": 2.6,
        "销量": 2.6,
        "出货": 1.8,
        "财务": 2.2,
        "财务业绩": 2.6,
        "经营": 1.8,
        "收入": 1.6,
        "业绩": 1.5,
    },
}

_CONNECTOR_KEYWORDS = ("对比", "对照", "联查", "关联", "联合", "同时", "一起", "匹配", "结合", "跨域", "支撑", "覆盖", "影响")
_ROUTE_THRESHOLD = 2.5
_ALLOWED_ROUTES = {"production", "planning", "inventory", "demand", "sales", "cross_domain", "legacy"}


def _domain_score(question: str, domain: str) -> tuple[float, list[str]]:
    score = 0.0
    table_hits: list[str] = []
    q = question.lower()
    for table_name in get_tables_for_domain(domain):
        if table_name.lower() in q:
            score += 3.0
            table_hits.append(table_name)
    for keyword, weight in _DOMAIN_KEYWORDS[domain].items():
        if keyword.lower() in q:
            score += weight
    return score, table_hits


def _suggest_tables(domain: str, question: str) -> list[str]:
    q = question.lower()
    if domain == "production":
        if any(token in q for token in ("报废", "不良", "产出", "实绩", "投入")):
            return ["production_actuals", "product_attributes", "product_mapping"]
        return ["production_actuals", "product_attributes", "product_mapping"]
    if domain == "planning":
        if any(token in q for token in ("周计划", "周排产", "滚动计划", "版本", "周滚")):
            return ["weekly_rolling_plan", "product_attributes", "product_mapping"]
        if any(token in q for token in ("月计划", "月度计划", "审批版")):
            return ["monthly_plan_approved", "product_attributes", "product_mapping"]
        return ["daily_PLAN", "product_attributes", "product_mapping"]
    if domain == "inventory":
        if any(token in q for token in ("在途", "hub", "客户端库存", "客户仓", "oms", "库龄", "期初")):
            return ["oms_inventory", "product_attributes"]
        if any(token in q for token in ("ttl", "hold", "库位", "erp", "checkincode")):
            return ["daily_inventory", "product_attributes", "product_mapping"]
        if any(token in q for token in ("齐套", "支撑", "缺料")):
            return ["daily_inventory", "oms_inventory", "product_attributes"]
        return ["daily_inventory", "product_attributes", "product_mapping"]
    if domain == "demand":
        if any(token in q for token in ("v版", "forecast", "原始需求", "客户需求")):
            return ["v_demand", "product_attributes", "product_mapping"]
        if any(token in q for token in ("p版", "commit", "承诺需求", "承诺")):
            return ["p_demand", "product_attributes", "product_mapping"]
        return ["p_demand", "v_demand", "product_attributes"]
    if domain == "sales":
        return ["sales_financial_perf", "product_attributes", "product_mapping"]
    return []


def _build_tables_for_route(route: str, matched_domains: list[str], explicit_hits: list[str], scored: list[tuple[str, float, list[str]]], question: str) -> list[str]:
    tables: list[str] = []
    if route == "cross_domain":
        for domain in matched_domains[:2]:
            for table_name in explicit_hits + _suggest_tables(domain, question):
                if table_name not in tables:
                    tables.append(table_name)
        return tables

    for domain, _, domain_hits in scored:
        if domain != route:
            continue
        for table_name in explicit_hits + domain_hits:
            if table_name not in tables:
                tables.append(table_name)
        break
    if not tables and route in {"production", "planning", "inventory", "demand", "sales"}:
        tables = _suggest_tables(route, question)
    return tables


def _should_use_llm_router(rule_decision: RouteDecision, scored: list[tuple[str, float, list[str]]], question: str) -> bool:
    if rule_decision.route == "legacy" and any(token in question for token in ("查询", "统计", "分析", "对比", "看下", "查看", "多少", "趋势", "风险")):
        return True
    if len(scored) < 2:
        return False
    top_score = scored[0][1]
    second_score = scored[1][1]
    if top_score < _ROUTE_THRESHOLD + 0.8:
        return True
    if top_score > 0 and second_score >= top_score * 0.8:
        return True
    return False


def _llm_route_question(question: str, shared_filters: dict, explicit_hits: list[str], scored: list[tuple[str, float, list[str]]]) -> RouteDecision | None:
    prompt = build_route_decision_prompt(
        question=question,
        shared_filters=shared_filters,
        explicit_hits=explicit_hits,
        scored_domains=[(domain, score) for domain, score, _ in scored],
    )
    raw = llm_complete(prompt)
    try:
        payload = json.loads(raw)
    except Exception:
        return None

    route = (payload.get("route") or "").strip()
    if route not in _ALLOWED_ROUTES:
        return None

    confidence = payload.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except Exception:
        confidence = 0.0
    confidence = max(0.0, min(0.95, confidence))

    matched_domains = payload.get("matched_domains") or []
    if not isinstance(matched_domains, list):
        matched_domains = []
    matched_domains = [str(domain) for domain in matched_domains if str(domain) in {"production", "planning", "inventory", "demand", "sales"}]

    if route == "cross_domain" and len(matched_domains) < 2:
        return None
    if route in {"production", "planning", "inventory", "demand", "sales"} and route not in matched_domains:
        matched_domains = [route]
    if route == "legacy":
        matched_domains = []

    reason = (payload.get("reason") or "").strip() or f"llm fallback selected {route}"
    tables = _build_tables_for_route(route, matched_domains, explicit_hits, scored, question)

    return RouteDecision(
        route=route,
        confidence=confidence,
        matched_domains=matched_domains,
        target_tables=tables,
        filters=shared_filters,
        reason=reason,
    )


def route_question_by_rules(question: str) -> tuple[RouteDecision, list[tuple[str, float, list[str]]], list[str], dict]:
    q = (question or "").strip()
    if not q:
        return RouteDecision(route="legacy", reason="empty question"), [], [], {}
    shared_filters = extract_shared_filters(q)

    explicit_hits = explicit_table_hits(q)
    scored: list[tuple[str, float, list[str]]] = []
    for domain in ("production", "planning", "inventory", "demand", "sales"):
        score, domain_table_hits = _domain_score(q, domain)
        scored.append((domain, score, domain_table_hits))

    scored.sort(key=lambda item: item[1], reverse=True)
    top_domain, top_score, top_table_hits = scored[0]
    second_domain, second_score, second_table_hits = scored[1]

    active_domains = [domain for domain, score, _ in scored if score >= _ROUTE_THRESHOLD]
    cross_domain_signal = any(token in q for token in _CONNECTOR_KEYWORDS)

    if (
        len(active_domains) > 1 and (cross_domain_signal or second_score >= top_score * 0.65)
    ) or (
        cross_domain_signal and top_score >= 2.0 and second_score >= 1.5
    ) or (
        top_score >= 2.5 and second_score >= 1.8 and cross_domain_signal
    ):
        matched_domains = list(active_domains) if len(active_domains) > 1 else [top_domain, second_domain]
        combined_tables: list[str] = []
        for table_name in explicit_hits + top_table_hits + second_table_hits:
            if table_name not in combined_tables:
                combined_tables.append(table_name)
        if not combined_tables:
            combined_tables.extend(_suggest_tables(top_domain, q))
            for table_name in _suggest_tables(second_domain, q):
                if table_name not in combined_tables:
                    combined_tables.append(table_name)
        return RouteDecision(
            route="cross_domain",
            confidence=min(0.95, top_score / 10.0),
            matched_domains=matched_domains,
            target_tables=combined_tables,
            filters=shared_filters,
            reason=f"question spans {', '.join(matched_domains)}",
        ), scored, explicit_hits, shared_filters

    if top_score >= _ROUTE_THRESHOLD:
        tables: list[str] = []
        for table_name in explicit_hits + top_table_hits:
            if table_name not in tables:
                tables.append(table_name)
        if not tables:
            tables = _suggest_tables(top_domain, q)
        return RouteDecision(
            route=top_domain,
            confidence=min(0.95, top_score / 10.0),
            matched_domains=[top_domain],
            target_tables=tables,
            filters=shared_filters,
            reason=f"matched {top_domain} keywords",
        ), scored, explicit_hits, shared_filters

    return RouteDecision(
        route="legacy",
        confidence=min(0.4, top_score / 10.0),
        matched_domains=[top_domain] if top_score > 0 else [],
        target_tables=explicit_hits,
        filters=shared_filters,
        reason="router confidence too low",
    ), scored, explicit_hits, shared_filters


def route_question(question: str) -> RouteDecision:
    rule_decision, scored, explicit_hits, shared_filters = route_question_by_rules(question)
    if not scored:
        return rule_decision
    if not _should_use_llm_router(rule_decision, scored, question):
        return rule_decision
    llm_decision = _llm_route_question(question, shared_filters, explicit_hits, scored)
    if llm_decision is None:
        return rule_decision
    llm_decision.reason = llm_decision.reason or f"llm fallback selected {llm_decision.route}"
    return llm_decision


__all__ = ["route_question", "route_question_by_rules"]
