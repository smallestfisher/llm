import re
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

from core.config.loader import load_lexicon


LEXICON: Dict[str, str] = load_lexicon()


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def normalize_question(question: str, min_ratio: float = 0.84) -> Tuple[str, List[str]]:
    """
    将黑话/简称归一化到标准表或字段名，返回增强问题与命中词列表。
    """
    q = question
    hits: List[str] = []

    # 1) 直接替换命中
    for k, v in LEXICON.items():
        if k in q:
            q = q.replace(k, f"{k}({v})")
            hits.append(k)

    # 2) 模糊匹配：对未命中的短词做近似映射
    # 仅对中文词段做粗略匹配，避免误伤数字/英文
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}", q)
    for tok in tokens:
        if tok in hits:
            continue
        best = None
        best_score = 0.0
        for k in LEXICON.keys():
            score = _similar(tok, k)
            if score > best_score:
                best_score = score
                best = k
        if best and best_score >= min_ratio:
            q = q.replace(tok, f"{tok}({LEXICON[best]})")
            hits.append(tok)

    return q, hits
