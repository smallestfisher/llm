from __future__ import annotations

import json


def _format_lines(items: tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items if item)


def _build_demand_version_hint(structured_filters: dict) -> str:
    exact = str((structured_filters or {}).get("pm_version_exact") or "")
    prefix = str((structured_filters or {}).get("pm_version_prefix") or "")
    table_type = str((structured_filters or {}).get("pm_version_table_type") or "")
    if not exact and not prefix:
        return ""

    lines = [
        "Demand 版本规则：PM_VERSION 与时间相关，常见格式为 YYYYMMWn + 表类型/版次。",
    ]
    if exact:
        lines.append(f"当前问题已有完整版本号，必须使用 PM_VERSION = '{exact}' 精确过滤。")
    elif prefix:
        if table_type in {"P", "V"}:
            lines.append(f"当前问题已归一为周前缀 {prefix}，应优先使用 PM_VERSION LIKE '{prefix}{table_type}%'。")
        else:
            lines.append(f"当前问题已归一为周前缀 {prefix}，应优先使用 PM_VERSION LIKE '{prefix}%'.")
    lines.append("若只有月粒度时间且没有 pm_version_prefix/pm_version_exact，不要臆造某一周的 PM_VERSION。")
    return "\n".join(f"- {line}" for line in lines)


GLOBAL_SQL_CONSTRAINTS = (
    "只输出纯 SQL，不要输出解释。",
    "只能使用 SELECT 或 WITH + SELECT。",
    "不要使用不存在的字段或表。",
    "如果需要关联，优先遵循 schema 中已有的 relationships。",
    "除非用户明确要求，不要返回无界全表扫描结果。",
    "如果【结构化过滤条件】存在时间/版本/工厂/客户/产品条件，优先在 SQL 中准确体现。",
)


GLOBAL_ANSWER_STYLE = (
    "回答固定 3 段：结论(1-2句) -> 关键数字(最多3条) -> 风险/建议(可选1条)。",
    "短句输出，避免重复和铺陈。",
    "每条关键数字必须可映射到结果字段和值；缺少证据时写“未查到”。",
)


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
    global_text = _format_lines(GLOBAL_SQL_CONSTRAINTS)
    filter_text = json.dumps(structured_filters or {}, ensure_ascii=False, indent=2)
    demand_hint = _build_demand_version_hint(structured_filters or {})
    return f"""你是一个资深的制造企业 MySQL 8.0 专家，当前负责 {domain_label} 技能。

【全局约束】
{global_text}

当前业务关注点：
{focus_text}

字段与业务口径：
{convention_text}

请根据【表结构】和【SQL 规则】将用户问题转换成只读 SQL。

【表结构】
{table_schema}

【结构化过滤条件】
{filter_text}

【版本时间规则】
{demand_hint or "- 无额外版本时间约束"}

【SQL 规则】
{rule_text}

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
    demand_hint = _build_demand_version_hint(structured_filters or {})
    return f"""你是 {domain_label} 技能的 MySQL 修复助手。刚才生成的 SQL 执行失败了。

【问题】
{question}

【表结构】
{table_schema}

【字段与业务口径】
{convention_text}

【结构化过滤条件】
{filter_text}

【版本时间规则】
{demand_hint or "- 无额外版本时间约束"}

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
    style_text = _format_lines(GLOBAL_ANSWER_STYLE)
    return f"""你是一个 {domain_label} 数据分析助理。
请根据用户问题、SQL 和数据库结果，输出专业且简洁的业务回答。

【回答规则】
{rule_text}

【统一风格】
{style_text}

【证据绑定要求】
- 只使用给定结果中的字段和数值，不得补充未出现的数据。
- 关键数字需写明来源字段（例如: 来自 report_month=2026-03 的 sales_qty）。
- 如果结果为空，必须直接输出“未查到数据”，不要给建议或猜测。

用户问题：{{question}}
执行 SQL：{{sql_query}}
数据库返回预览：{{db_result}}
统计分析结果：{{data_summary}}
证据映射：{{evidence_json}}
"""


def build_route_decision_prompt(
    *,
    question: str,
    shared_filters: dict,
    explicit_hits: list[str],
    scored_domains: list[dict],
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
5. top2 置信接近时，优先参考 positive_hits/negative_hits 做保守判断。

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


def build_disambiguation_prompt(
    *,
    question: str,
    route: str,
    structured_filters: dict,
    candidate_options: list[dict[str, str]],
) -> str:
    return f"""你是企业数据 Copilot 的澄清判定器。
你的任务不是写 SQL，而是判断当前信息是否足够在候选口径中做出安全选择。

规则：
1. 只输出裸 JSON，不要输出解释。
2. 如果问题已经足够明确，请输出 status=resolved，并给出 chosen_option。
3. 如果信息不足以安全判断，请输出 status=clarify，并给出用户可直接回答的 question。
4. 如果当前根本不需要澄清，请输出 status=not_needed。
5. 不要输出候选范围之外的 chosen_option。

当前 route：
{route}

结构化过滤条件：
{json.dumps(structured_filters or {}, ensure_ascii=False, indent=2)}

候选口径：
{json.dumps(candidate_options or [], ensure_ascii=False, indent=2)}

用户问题：
{question}

输出 JSON 结构：
{{
  "status": "resolved | clarify | not_needed",
  "chosen_option": "candidate_id or empty",
  "question": "需要澄清时返回给用户的问题，否则为空",
  "reason": "简短原因"
}}
"""
