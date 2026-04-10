from __future__ import annotations

from core.router.filter_extractor import extract_shared_filters
from core.registry.tables import explicit_table_hits, get_tables_for_domain
from core.runtime.state import RouteDecision


_DOMAIN_KEYWORDS = {
    "production": {
        "生产": 2.0,
        "排产": 2.0,
        "计划": 1.2,
        "月计划": 2.0,
        "周计划": 2.0,
        "实绩": 2.0,
        "产出": 1.5,
        "产线": 1.8,
        "线别": 1.6,
        "良率": 2.2,
        "不良": 2.0,
        "停机": 2.0,
        "投料": 1.5,
        "工序": 1.5,
        "在制": 1.6,
        "wip": 1.6,
        "需求": 1.3,
        "forecast": 1.6,
        "commit": 1.6,
        "交付": 1.0,
        "销售": 1.1,
        "营收": 1.4,
        "风险": 0.4,
    },
    "inventory": {
        "库存": 2.4,
        "可用库存": 2.4,
        "安全库存": 2.2,
        "在途": 2.0,
        "hub": 2.0,
        "缺货": 2.0,
        "齐套": 2.0,
        "仓库": 1.8,
        "仓": 1.2,
        "备货": 1.4,
        "客户仓": 2.0,
        "库存覆盖": 2.0,
        "oms": 2.2,
        "wip": 1.0,
        "在制": 1.0,
        "风险": 0.4,
        "缺料": 2.0,
    },
}

_CONNECTOR_KEYWORDS = ("对比", "联查", "关联", "联合", "同时", "一起", "匹配", "结合", "跨域")
_ROUTE_THRESHOLD = 2.5


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
        if any(token in q for token in ("良率", "不良", "停机", "产出", "实绩")):
            return ["production_actuals", "product_attributes", "product_mapping"]
        if any(token in q for token in ("周计划", "周排产", "调整原因")):
            return ["weekly_rolling_plan", "product_attributes", "product_mapping"]
        if any(token in q for token in ("月计划", "月度计划")):
            return ["monthly_plan_approved", "product_attributes", "product_mapping"]
        if any(token in q for token in ("需求", "forecast", "commit")):
            return ["p_demand", "v_demand", "product_attributes"]
        if any(token in q for token in ("在制", "wip", "批次", "工序")):
            return ["work_in_progress", "product_attributes", "product_mapping"]
        return ["daily_schedule", "product_attributes", "product_mapping"]
    if domain == "inventory":
        if any(token in q for token in ("在途", "hub", "客户端库存", "客户仓", "oms")):
            return ["oms_inventory", "product_attributes"]
        if any(token in q for token in ("排产", "齐套", "支撑")):
            return ["daily_inventory", "daily_schedule", "work_in_progress", "product_attributes"]
        if any(token in q for token in ("在制", "wip")):
            return ["work_in_progress", "daily_inventory", "product_attributes"]
        return ["daily_inventory", "product_attributes", "product_mapping"]
    return []


def route_question(question: str) -> RouteDecision:
    q = (question or "").strip()
    if not q:
        return RouteDecision(route="legacy", reason="empty question")
    shared_filters = extract_shared_filters(q)

    explicit_hits = explicit_table_hits(q)
    scored: list[tuple[str, float, list[str]]] = []
    for domain in ("production", "inventory"):
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
        )

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
        )

    return RouteDecision(
        route="legacy",
        confidence=min(0.4, top_score / 10.0),
        matched_domains=[top_domain] if top_score > 0 else [],
        target_tables=explicit_hits,
        filters=shared_filters,
        reason="router confidence too low",
    )
