from core.config.loader import load_normalization_aliases


def normalize_question(question: str):
    """对高频业务别名做轻量归一化，返回归一化后的问句和命中的别名信息。"""
    normalized = question
    hits = []

    alias_pairs = []
    for canonical, aliases in load_normalization_aliases().items():
        for alias in aliases:
            alias_pairs.append((alias, canonical))

    # 长词优先，避免短词提前替换影响命中。
    for alias, canonical in sorted(alias_pairs, key=lambda item: len(item[0]), reverse=True):
        if alias in normalized:
            hits.append({"alias": alias, "canonical": canonical})
            normalized = normalized.replace(alias, canonical)

    return normalized, hits
