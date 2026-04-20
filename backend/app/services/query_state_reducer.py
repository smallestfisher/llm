from __future__ import annotations

from typing import Any

_REPLACE_OPS = {"replace_state", "new_query", "switch_query"}
_DOMAIN_OPS = {"switch_domain"}
_DIMENSION_ADD_OPS = {"add_dimension", "add_dimensions"}
_DIMENSION_REMOVE_OPS = {"remove_dimension", "remove_dimensions"}
_DIMENSION_SET_OPS = {"set_dimensions"}
_FILTER_SET_OPS = {"set_filter", "set_filters", "replace_filters"}
_FILTER_REMOVE_OPS = {"remove_filter", "remove_filters"}
_PRESENTATION_SET_OPS = {"set_presentation", "set_detail_level", "set_show_fields"}
_PRESENTATION_REMOVE_OPS = {"remove_presentation", "clear_presentation_field"}
_PATCH_OPS = {
    "patch_state",
    "refine_query",
    "refine_presentation",
    *(_DOMAIN_OPS | _DIMENSION_ADD_OPS | _DIMENSION_REMOVE_OPS | _DIMENSION_SET_OPS | _FILTER_SET_OPS | _FILTER_REMOVE_OPS | _PRESENTATION_SET_OPS | _PRESENTATION_REMOVE_OPS),
}


class QueryStateReducer:
    def apply(self, previous_state: dict[str, Any] | None, query_op: dict[str, Any] | None, planned_state: dict[str, Any] | None) -> dict[str, Any]:
        prev = self._normalize_state(previous_state)
        op = dict(query_op or {}) if isinstance(query_op, dict) else {}
        planned = self._normalize_state(planned_state)
        op_type = str(op.get("type") or "replace_state").strip()
        if op_type in _REPLACE_OPS:
            return self._finalize(planned or prev)
        if op_type in _PATCH_OPS:
            merged = self._patch(prev, op, planned)
            return self._finalize(merged)
        return self._finalize(planned or prev)

    def _patch(self, previous_state: dict[str, Any], query_op: dict[str, Any], planned_state: dict[str, Any]) -> dict[str, Any]:
        merged = self._normalize_state(previous_state)
        changes = dict(query_op.get("changes") or {})
        op_type = str(query_op.get("type") or "patch_state").strip()

        if planned_state.get("query_text"):
            merged["query_text"] = planned_state["query_text"]
        if planned_state.get("metric"):
            merged["metric"] = planned_state["metric"]
        if planned_state.get("intent"):
            merged["intent"] = planned_state["intent"]

        if op_type in _DOMAIN_OPS and planned_state.get("domain"):
            merged["domain"] = planned_state["domain"]
            merged["domains"] = self._dedupe_strings(planned_state.get("domains")) or ([planned_state["domain"]] if planned_state["domain"] else [])
        elif planned_state.get("domain") and not merged.get("domain"):
            merged["domain"] = planned_state["domain"]
            merged["domains"] = self._dedupe_strings(planned_state.get("domains")) or ([planned_state["domain"]] if planned_state["domain"] else [])

        dimensions = self._dedupe_strings(merged.get("dimensions"))
        if op_type in _DIMENSION_SET_OPS:
            dimensions = self._dedupe_strings(changes.get("dimensions") or planned_state.get("dimensions"))
        else:
            if op_type in _DIMENSION_REMOVE_OPS:
                dimensions = self._apply_list_patch(dimensions, changes.get("dimensions") or changes.get("dimensions_remove") or planned_state.get("dimensions"), remove=True)
            else:
                dimensions = self._apply_list_patch(dimensions, changes.get("dimensions_remove"), remove=True)
            if op_type in _DIMENSION_ADD_OPS:
                dimensions = self._apply_list_patch(dimensions, changes.get("dimensions") or changes.get("dimensions_add") or planned_state.get("dimensions"), remove=False)
            else:
                dimensions = self._apply_list_patch(dimensions, changes.get("dimensions_add"), remove=False)
        merged["dimensions"] = dimensions

        filters = dict(merged.get("filters") or {})
        if op_type in _FILTER_SET_OPS:
            filters.update(dict(changes.get("filters") or changes.get("filters_set") or planned_state.get("filters") or {}))
        else:
            filters.update(dict(changes.get("filters_set") or {}))
            if planned_state.get("filters"):
                filters.update(dict(planned_state.get("filters") or {}))
        remove_filters = changes.get("filters_remove")
        if op_type in _FILTER_REMOVE_OPS:
            remove_filters = changes.get("filters") or changes.get("filters_remove")
        for key in self._normalize_string_list(remove_filters):
            filters.pop(key, None)
        merged["filters"] = filters

        presentation = dict(merged.get("presentation") or {})
        if op_type in _PRESENTATION_SET_OPS:
            presentation.update(dict(changes.get("presentation") or changes.get("presentation_set") or planned_state.get("presentation") or {}))
        else:
            presentation.update(dict(changes.get("presentation_set") or {}))
            if planned_state.get("presentation"):
                presentation.update(dict(planned_state.get("presentation") or {}))
        remove_presentation = changes.get("presentation_remove")
        if op_type in _PRESENTATION_REMOVE_OPS:
            remove_presentation = changes.get("presentation") or changes.get("presentation_remove")
        for key in self._normalize_string_list(remove_presentation):
            presentation.pop(key, None)
        merged["presentation"] = presentation

        return merged

    def _finalize(self, state: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_state(state)
        show_fields = self._dedupe_strings(normalized.get("presentation", {}).get("show_fields"))
        normalized["presentation"]["show_fields"] = show_fields
        normalized["dimensions"] = self._dedupe_strings(normalized.get("dimensions"))
        return normalized

    def _normalize_state(self, state: dict[str, Any] | None) -> dict[str, Any]:
        data = dict(state or {}) if isinstance(state, dict) else {}
        return {
            "state_version": int(data.get("state_version") or 1),
            "domain": str(data.get("domain") or "").strip(),
            "domains": self._dedupe_strings(data.get("domains")),
            "metric": str(data.get("metric") or "").strip(),
            "intent": str(data.get("intent") or "").strip(),
            "query_text": str(data.get("query_text") or "").strip(),
            "dimensions": self._dedupe_strings(data.get("dimensions")),
            "filters": dict(data.get("filters") or {}),
            "presentation": dict(data.get("presentation") or {}),
            "raw_question": str(data.get("raw_question") or "").strip(),
            "previous_query_text": str(data.get("previous_query_text") or "").strip(),
        }

    def _apply_list_patch(self, base: list[str], values: Any, *, remove: bool) -> list[str]:
        current = self._dedupe_strings(base)
        for item in self._normalize_string_list(values):
            if remove:
                current = [row for row in current if row != item]
            elif item not in current:
                current.append(item)
        return current

    @staticmethod
    def _normalize_string_list(value: Any) -> list[str]:
        rows = value if isinstance(value, list) else []
        return [str(item).strip() for item in rows if str(item).strip()]

    @staticmethod
    def _dedupe_strings(value: Any) -> list[str]:
        result: list[str] = []
        for item in value if isinstance(value, list) else []:
            text = str(item).strip()
            if text and text not in result:
                result.append(text)
        return result
