from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.execution.llm_client import llm_complete
from app.execution.prompts import build_disambiguation_prompt
from app.execution.sql_guard import safe_json_loads


@dataclass(slots=True)
class DisambiguationDecision:
    status: str = "not_needed"
    question: str = ""
    reason: str = ""
    chosen_option: str = ""
    clarification_type: str = ""
    clarification_options: list[str] = field(default_factory=list)
    clarification_context: dict[str, Any] = field(default_factory=dict)
    updated_filters: dict[str, Any] = field(default_factory=dict)

    def to_state_update(self) -> dict[str, Any]:
        return {
            "needs_clarification": self.status == "clarify",
            "clarification_question": self.question,
            "clarification_options": self.clarification_options,
            "clarification_type": self.clarification_type,
            "clarification_context": self.clarification_context,
            "disambiguation_status": self.status,
            "disambiguation_reason": self.reason,
            "refined_filters": self.updated_filters,
        }


def _demand_candidates(question: str, route: str, filters: dict[str, Any], allowed_tables: list[str]) -> list[dict[str, str]]:
    if route != "demand":
        return []
    allowed = set(allowed_tables or [])
    if "p_demand" not in allowed or "v_demand" not in allowed:
        return []

    lowered = (question or "").lower()
    explicit_type = bool(filters.get("pm_version_table_type")) or any(
        token in lowered for token in ("v版", "forecast", "p版", "commit", "承诺")
    )
    if explicit_type:
        return []

    return [
        {"id": "v_demand", "label": "V版 forecast", "description": "面向 forecast / 预计 / 预测需求口径。"},
        {"id": "p_demand", "label": "P版承诺需求", "description": "面向 commit / 承诺需求口径。"},
    ]


def _resolved_filter_update(chosen_option: str, filters: dict[str, Any]) -> dict[str, Any]:
    updated = dict(filters or {})
    if chosen_option == "v_demand":
        updated["table"] = "v_demand"
        updated["pm_version_table_type"] = "V"
    elif chosen_option == "p_demand":
        updated["table"] = "p_demand"
        updated["pm_version_table_type"] = "P"
    return updated


def resolve_disambiguation(
    *,
    question: str,
    route: str,
    structured_filters: dict[str, Any],
    allowed_tables: list[str],
) -> DisambiguationDecision:
    filters = dict(structured_filters or {})
    candidates = _demand_candidates(question, route, filters, allowed_tables)
    if not candidates:
        return DisambiguationDecision(updated_filters=filters)

    prompt = build_disambiguation_prompt(
        question=question,
        route=route,
        structured_filters=filters,
        candidate_options=candidates,
    )
    try:
        payload = safe_json_loads(llm_complete(prompt, task="disambiguate"))
    except Exception:
        payload = {}

    status = str(payload.get("status") or "").strip().lower()
    if status not in {"resolved", "clarify", "not_needed"}:
        status = "clarify"

    chosen_option = str(payload.get("chosen_option") or "").strip()
    valid_options = {item["id"] for item in candidates}
    if chosen_option not in valid_options:
        chosen_option = ""

    if status == "resolved" and chosen_option:
        return DisambiguationDecision(
            status="resolved",
            chosen_option=chosen_option,
            reason=str(payload.get("reason") or "").strip(),
            updated_filters=_resolved_filter_update(chosen_option, filters),
        )

    if status == "not_needed":
        return DisambiguationDecision(
            status="not_needed",
            reason=str(payload.get("reason") or "").strip(),
            updated_filters=filters,
        )

    return DisambiguationDecision(
        status="clarify",
        question=str(payload.get("question") or "").strip()
        or "你这里说的需求口径是 V版 forecast，还是 P版承诺需求？请直接回复“V版”或“P版”。",
        reason=str(payload.get("reason") or "").strip() or "candidate scope still ambiguous",
        clarification_type="table_choice",
        clarification_options=[item["label"] for item in candidates],
        clarification_context={
            "route": route,
            "original_question": question,
            "candidate_options": candidates,
        },
        updated_filters=filters,
    )


def resolve_clarification_reply(metadata: dict[str, Any], user_reply: str) -> str:
    if not metadata.get("needs_clarification"):
        return user_reply
    if metadata.get("clarification_type") != "table_choice":
        return user_reply

    context = dict(metadata.get("clarification_context") or {})
    original_question = str(context.get("original_question") or "").strip()
    options = list(context.get("candidate_options") or [])
    if not original_question or not options:
        return user_reply

    lowered = (user_reply or "").strip().lower()
    choice_map = {
        "v_demand": ("v版", "forecast"),
        "p_demand": ("p版", "commit", "承诺"),
    }
    chosen_option = ""
    for option in options:
        option_id = str(option.get("id") or "")
        if any(token in lowered for token in choice_map.get(option_id, ())):
            chosen_option = option_id
            break
    if not chosen_option:
        return user_reply

    supplement = "V版 forecast" if chosen_option == "v_demand" else "P版承诺需求"
    return f"{original_question}\n补充说明：这里指{supplement}。"
