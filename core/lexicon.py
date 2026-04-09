CANONICAL_TERM_ALIASES = {
    "产出": ["产量", "产出量", "实际产出", "实际产量"],
    "良率": ["直通率", "合格率"],
    "不良率": ["坏品率", "缺陷率"],
    "异常": ["风险", "告警", "预警", "问题"],
    "停线": ["停机", "停产", "线停"],
    "瓶颈": ["卡点", "堵点"],
    "积压": ["堆积", "压货"],
    "在制品": ["wip", "在制"],
    "库存": ["在库", "存货"],
    "排产": ["计划排产", "排程"],
    "需求": ["需求量", "要货", "forecast"],
    "承诺产能": ["承诺", "产能承诺"],
    "周计划": ["周排产", "周安排"],
    "日计划": ["日排产", "日安排"],
    "实绩": ["实际", "达成", "完成情况"],
}


def normalize_question(question: str):
    """对高频业务别名做轻量归一化，返回归一化后的问句和命中的别名信息。"""
    normalized = question
    hits = []

    alias_pairs = []
    for canonical, aliases in CANONICAL_TERM_ALIASES.items():
        for alias in aliases:
            alias_pairs.append((alias, canonical))

    # 长词优先，避免短词提前替换影响命中。
    for alias, canonical in sorted(alias_pairs, key=lambda item: len(item[0]), reverse=True):
        if alias in normalized:
            hits.append({"alias": alias, "canonical": canonical})
            normalized = normalized.replace(alias, canonical)

    return normalized, hits
