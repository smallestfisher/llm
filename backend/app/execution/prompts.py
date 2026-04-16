from __future__ import annotations

import json


def _format_lines(items: tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items if item)


def build_guard_prompt(*, domain_label: str, guard_scope: str, question: str) -> str:
    return f"""你是一个企业数据 Copilot 的安全守卫。
当前技能负责的业务域：{domain_label}
允许处理的业务范围：{guard_scope}

如果用户输入明显是闲聊、攻击、越权、与企业经营数据无关的问题，请返回 "REJECT"。
如果问题属于正常的数据查询、统计、比对、分析需求，请返回 "PASS"。

用户输入: {question}
"""


def build_text2sql_prompt(
    *,
    domain_label: str,
    focus_areas: tuple[str, ...],
    field_conventions: tuple[str, ...],
    sql_rules: tuple[str, ...],
    table_schema: str,
    question: str,
    structured_filters: dict,
) -> str:
    focus_text = _format_lines(focus_areas)
    convention_text = _format_lines(field_conventions)
    rule_text = _format_lines(sql_rules)
    filter_text = json.dumps(structured_filters or {}, ensure_ascii=False, indent=2)
    return f"""你是一个资深的制造企业 MySQL 8.0 专家，当前负责 {domain_label} 技能。

当前业务关注点：
{focus_text}

字段与业务口径：
{convention_text}

请根据【表结构】和【SQL 规则】将用户问题转换成只读 SQL。

【表结构】
{table_schema}

【结构化过滤条件】
{filter_text}

【SQL 规则】
{rule_text}

【硬性约束】
1. 只输出纯 SQL，不要输出解释。
2. 只能使用 SELECT 或 WITH + SELECT。
3. 不要使用不存在的字段或表。
4. 如果需要关联，优先遵循 schema 中已有的 relationships。
5. 除非用户明确要求，不要返回无界全表扫描结果。
6. 如果【结构化过滤条件】中存在时间、版本、工厂、客户或产品条件，优先在 SQL 中准确体现。

用户问题：
{question}
"""


def build_reflect_sql_prompt(
    *,
    domain_label: str,
    field_conventions: tuple[str, ...],
    sql_rules: tuple[str, ...],
    question: str,
    table_schema: str,
    sql_query: str,
    error_message: str,
    structured_filters: dict,
) -> str:
    convention_text = _format_lines(field_conventions)
    rule_text = _format_lines(sql_rules)
    filter_text = json.dumps(structured_filters or {}, ensure_ascii=False, indent=2)
    return f"""你是 {domain_label} 技能的 MySQL 修复助手。刚才生成的 SQL 执行失败了。

【问题】
{question}

【表结构】
{table_schema}

【字段与业务口径】
{convention_text}

【结构化过滤条件】
{filter_text}

【SQL 规则】
{rule_text}

【失败 SQL】
{sql_query}

【报错信息】
{error_message}

请修复 SQL，只输出修复后的纯 SQL，不要输出解释。
"""


def build_answer_prompt(
    *,
    domain_label: str,
    answer_rules: tuple[str, ...],
) -> str:
    rule_text = _format_lines(answer_rules)
    return f"""你是一个 {domain_label} 数据分析助理。
请根据用户问题、SQL 和数据库结果，输出专业、简洁、可执行的业务回答。

【回答规则】
{rule_text}

用户问题：{{question}}
执行 SQL：{{sql_query}}
数据库返回预览：{{db_result}}
统计分析结果：{{data_summary}}
"""


def build_route_decision_prompt(
    *,
    question: str,
    shared_filters: dict,
    explicit_hits: list[str],
    scored_domains: list[tuple[str, float]],
) -> str:
    return f"""你是企业制造数据 Copilot 的路由决策器。
请判断用户问题应该进入哪个业务域。

允许的 route 只有：
- production
- planning
- inventory
- demand
- sales
- cross_domain
- legacy

规则：
1. 不要包含任何 Markdown 格式标记,仅输出裸JSON,不要输出解释文字。
2. 只有在问题确实同时涉及多个业务域、且需要联合回答时，才输出 cross_domain。
3. 如果问题与企业数据查询无关，或无法判断，输出 legacy。
4. 不要臆造表名，不要输出允许范围之外的 route。

用户问题：
{question}

已提取的共享过滤条件：
{json.dumps(shared_filters or {}, ensure_ascii=False, indent=2)}

显式表命中：
{json.dumps(explicit_hits or [], ensure_ascii=False)}

规则层打分摘要：
{json.dumps(scored_domains, ensure_ascii=False)}

请输出如下 JSON：
{{
  "route": "inventory",
  "confidence": 0.82,
  "matched_domains": ["inventory"],
  "reason": "..."
}}
"""
