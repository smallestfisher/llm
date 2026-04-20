from __future__ import annotations

import json
from typing import Any, Sequence

from app.execution.llm_client import llm_complete
from app.services.query_state_reducer import QueryStateReducer
from app.semantic.filters import extract_shared_filters

_ALLOWED_MODES = {"standalone_query", "query_refinement", "presentation_refinement", "ambiguous"}
_ALLOWED_DOMAINS = {"", "production", "planning", "inventory", "demand", "sales", "cross_domain", "general"}
_ALLOWED_OPS = {
    "replace_state",
    "patch_state",
    "new_query",
    "switch_query",
    "switch_domain",
    "set_dimensions",
    "add_dimension",
    "add_dimensions",
    "remove_dimension",
    "remove_dimensions",
    "set_filters",
    "replace_filters",
    "remove_filters",
    "set_presentation",
    "set_detail_level",
    "set_show_fields",
    "remove_presentation",
}


class ConversationResolver:
    def __init__(self) -> None:
        self.reducer = QueryStateReducer()

    def resolve(self, *, question: str, messages: Sequence[object]) -> dict[str, Any]:
        raw_question = (question or "").strip()
        previous_state = self.extract_latest_query_state(messages)
        parsed = self._plan_with_llm(raw_question=raw_question, previous_state=previous_state)
        if parsed is None:
            return self._fallback_plan(raw_question, previous_state)

        planned_state = self._normalize_query_state(
            parsed.get("query_state"),
            raw_question=raw_question,
            previous_state=previous_state,
        )
        query_op = self._normalize_query_op(
            parsed.get("query_op"),
            raw_question=raw_question,
            query_state=planned_state,
            previous_state=previous_state,
        )
        query_state = self.reducer.apply(previous_state, query_op, planned_state)
        mode = str(parsed.get("mode") or "standalone_query")
        if mode not in _ALLOWED_MODES:
            mode = "standalone_query"
        confidence = self._coerce_confidence(parsed.get("confidence"), default=0.75)
        reason = str(parsed.get("reason") or query_op.get("summary") or "conversation resolver planned query state")
        return {
            "state_version": 2,
            "mode": mode,
            "confidence": confidence,
            "reason": reason,
            "query_op": query_op,
            "query_state": query_state,
            "resolved_question": query_state.get("query_text") or raw_question,
            "resolved_route": query_state.get("domain") or "",
        }

    def extract_latest_resolved_request(self, messages: Sequence[object]) -> dict[str, Any] | None:
        for message in reversed(list(messages or [])):
            metadata = getattr(message, "metadata_dict", {}) or {}
            if not isinstance(metadata, dict):
                continue
            resolved = metadata.get("resolved_request")
            if isinstance(resolved, dict):
                return dict(resolved)
        return None

    def extract_latest_query_state(self, messages: Sequence[object]) -> dict[str, Any] | None:
        resolved = self.extract_latest_resolved_request(messages)
        if isinstance(resolved, dict):
            query_state = resolved.get("query_state")
            if isinstance(query_state, dict):
                return dict(query_state)
            legacy_question = str(resolved.get("resolved_question") or resolved.get("base_question") or resolved.get("raw_question") or "").strip()
            if legacy_question:
                return {
                    "domain": str(resolved.get("resolved_route") or resolved.get("route_hint") or ""),
                    "domains": [str(resolved.get("resolved_route") or resolved.get("route_hint") or "")] if resolved.get("resolved_route") or resolved.get("route_hint") else [],
                    "metric": "",
                    "intent": "",
                    "query_text": legacy_question,
                    "dimensions": list(resolved.get("dimensions") or []),
                    "filters": dict(resolved.get("filters") or {}),
                    "presentation": dict(resolved.get("presentation") or {}),
                }
        return None

    def _plan_with_llm(self, *, raw_question: str, previous_state: dict[str, Any] | None) -> dict[str, Any] | None:
        prompt = self._build_prompt(raw_question=raw_question, previous_state=previous_state)
        try:
            raw = llm_complete(prompt, task="router")
            payload = json.loads(raw)
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _build_prompt(self, *, raw_question: str, previous_state: dict[str, Any] | None) -> str:
        previous_json = json.dumps(previous_state or {}, ensure_ascii=False, indent=2, sort_keys=True)
        return f"""你是企业数据 Copilot 的会话状态规划器。你的任务不是回答问题，而是输出下一步要执行的结构化查询状态。

你必须判断当前用户输入是：
- standalone_query: 一个新的完整查询，替换当前活动查询状态
- query_refinement: 对上一轮查询条件或统计口径的修正
- presentation_refinement: 对上一轮结果展示字段/维度/明细粒度的修正
- ambiguous: 当前句子本身不完整，但显然依赖上一轮上下文

允许的 domain 只有：
- production
- planning
- inventory
- demand
- sales
- cross_domain
- general
- "" (未知)

输出要求：
1. 只输出裸 JSON，不要输出解释。
2. query_state 必须是“应用当前用户输入之后的完整下一状态”，不要只输出增量。
3. query_op.type 必须使用明确操作类型：new_query/switch_query/switch_domain/set_dimensions/add_dimensions/remove_dimensions/set_filters/remove_filters/set_presentation/set_detail_level/set_show_fields。
4. 仅在你无法精确表达操作时，才使用 replace_state 或 patch_state。
5. query_state.query_text 必须是一个完整、自包含、可直接执行的查询描述。
6. 如果当前输入是在补充显示字段，如“显示版本号/按工厂展开/看明细”，请把这些要求体现在 query_state.dimensions 或 query_state.presentation 中，而不是只写进 reason。
7. 如果当前输入明显切换到了另一个业务域的新问题，不要继承上一轮 domain/metric/filter。
8. filters 只保留结构化筛选条件，presentation 只保留展示/粒度/排序类约束。

上一轮活动查询状态（如果没有则为空对象）：
{previous_json}

当前用户输入：
{raw_question}

请输出如下 JSON：
{{
  "mode": "presentation_refinement",
  "confidence": 0.91,
  "reason": "current input modifies displayed dimensions of previous demand query",
  "query_op": {{
    "type": "add_dimensions",
    "summary": "add version dimension to previous demand query",
    "changes": {{
      "dimensions": ["version"],
      "presentation_set": {{"detail_level": "detail"}}
    }}
  }},
  "query_state": {{
    "domain": "demand",
    "domains": ["demand"],
    "metric": "本周预计需求",
    "intent": "demand_query",
    "query_text": "查询本周预计需求，并显示对应版本号",
    "dimensions": ["version"],
    "filters": {{"relative_week": "current_week"}},
    "presentation": {{"show_fields": ["version"], "detail_level": "summary"}}
  }}
}}"""

    def _normalize_query_state(
        self,
        state: Any,
        *,
        raw_question: str,
        previous_state: dict[str, Any] | None,
    ) -> dict[str, Any]:
        data = dict(state or {}) if isinstance(state, dict) else {}
        extracted_filters = extract_shared_filters(raw_question)
        filters = dict(previous_state.get("filters") or {}) if isinstance(previous_state, dict) else {}
        filters.update(dict(data.get("filters") or {}))
        filters.update(extracted_filters)

        domain = str(data.get("domain") or "").strip()
        if domain not in _ALLOWED_DOMAINS:
            domain = ""
        domains = [str(item).strip() for item in list(data.get("domains") or []) if str(item).strip() in _ALLOWED_DOMAINS and str(item).strip()]
        if domain and domain not in domains and domain != "cross_domain":
            domains = [domain]
        if domain == "cross_domain" and len(domains) < 2 and isinstance(previous_state, dict):
            prev_domains = [str(item).strip() for item in list(previous_state.get("domains") or []) if str(item).strip() in _ALLOWED_DOMAINS and str(item).strip()]
            if len(prev_domains) >= 2:
                domains = prev_domains

        query_text = str(data.get("query_text") or raw_question).strip()
        if not query_text and isinstance(previous_state, dict):
            query_text = str(previous_state.get("query_text") or raw_question).strip()

        return {
            "state_version": 1,
            "domain": domain,
            "domains": domains,
            "metric": str(data.get("metric") or "").strip(),
            "intent": str(data.get("intent") or "").strip(),
            "query_text": query_text,
            "dimensions": self._normalize_string_list(data.get("dimensions")),
            "filters": filters,
            "presentation": self._normalize_json_object(data.get("presentation")),
            "raw_question": raw_question,
            "previous_query_text": str((previous_state or {}).get("query_text") or "").strip(),
        }

    def _normalize_query_op(
        self,
        op: Any,
        *,
        raw_question: str,
        query_state: dict[str, Any],
        previous_state: dict[str, Any] | None,
    ) -> dict[str, Any]:
        data = dict(op or {}) if isinstance(op, dict) else {}
        op_type = str(data.get("type") or "replace_state").strip()
        if op_type not in _ALLOWED_OPS:
            op_type = "new_query" if not previous_state else "patch_state"
        if op_type == "replace_state" and previous_state:
            op_type = "switch_query"
        if op_type == "replace_state" and not previous_state:
            op_type = "new_query"
        op_family = "replace" if op_type in {"new_query", "switch_query", "replace_state"} else "patch"
        return {
            "type": op_type,
            "family": op_family,
            "summary": str(data.get("summary") or raw_question).strip(),
            "source_input": raw_question,
            "changes": self._normalize_json_object(data.get("changes")),
            "next_domain": query_state.get("domain") or "",
            "next_query_text": query_state.get("query_text") or raw_question,
        }

    def _fallback_plan(self, raw_question: str, previous_state: dict[str, Any] | None) -> dict[str, Any]:
        planned_state = {
            "state_version": 1,
            "domain": str((previous_state or {}).get("domain") or ""),
            "domains": list((previous_state or {}).get("domains") or []),
            "metric": "",
            "intent": "",
            "query_text": raw_question,
            "dimensions": [],
            "filters": extract_shared_filters(raw_question),
            "presentation": {},
            "raw_question": raw_question,
            "previous_query_text": str((previous_state or {}).get("query_text") or "").strip(),
        }
        query_op = {
            "type": "new_query",
            "summary": raw_question,
            "source_input": raw_question,
            "changes": {},
            "next_domain": planned_state.get("domain") or "",
            "next_query_text": planned_state.get("query_text") or raw_question,
        }
        query_state = self.reducer.apply(previous_state, query_op, planned_state)
        return {
            "state_version": 2,
            "mode": "standalone_query",
            "confidence": 0.3,
            "reason": "fallback standalone query state",
            "query_op": query_op,
            "query_state": query_state,
            "resolved_question": query_state["query_text"],
            "resolved_route": query_state.get("domain") or "",
        }

    @staticmethod
    def _normalize_string_list(value: Any) -> list[str]:
        items = value if isinstance(value, list) else []
        deduped: list[str] = []
        for item in items:
            text = str(item or "").strip()
            if text and text not in deduped:
                deduped.append(text)
        return deduped

    @staticmethod
    def _normalize_json_object(value: Any) -> dict[str, Any]:
        return dict(value or {}) if isinstance(value, dict) else {}

    @staticmethod
    def _coerce_confidence(value: Any, *, default: float) -> float:
        try:
            return max(0.0, min(0.99, float(value)))
        except Exception:
            return default
