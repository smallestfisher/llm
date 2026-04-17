from __future__ import annotations

import os
from abc import ABC
from typing import Any

from app.semantic.domains import build_schema_excerpt
from app.semantic.filters import apply_filter_refinement
from app.execution.llm_client import llm_complete
from app.execution.sql_executor import choose_best_sql_candidate, execute_sql
from app.execution.sql_guard import harden_sql, sanitize_sql
from app.presentation.answer_builder import build_answer_payload
from app.workflow.state import RouteDecision, SkillPlan, SkillResult, CancelledError
from app.execution.prompts import (
    build_answer_prompt,
    build_guard_prompt,
    build_reflect_sql_prompt,
    build_text2sql_prompt,
)
from app.skills.profiles import SKILL_PROFILES

SQL_CANDIDATE_COUNT = max(1, min(3, int(os.getenv("SQL_CANDIDATE_COUNT", "2"))))
SQL_CANDIDATE_EXPAND_SCORE = int(os.getenv("SQL_CANDIDATE_EXPAND_SCORE", "90"))


class BaseSkill(ABC):
    profile_key = ""
    domain = ""
    skill_name = ""
    node_name = ""
    domain_label = ""
    guard_scope = ""
    focus_areas: tuple[str, ...] = ()
    field_conventions: tuple[str, ...] = ()
    sql_rules: tuple[str, ...] = ()
    answer_rules: tuple[str, ...] = ()
    default_tables: tuple[str, ...] = ()
    helper_tables: tuple[str, ...] = ()
    keyword_table_map: tuple[tuple[tuple[str, ...], str], ...] = ()

    def __init__(self) -> None:
        profile = SKILL_PROFILES.get(self.profile_key)
        if profile is None:
            return
        self.domain_label = profile.domain_label
        self.guard_scope = profile.guard_scope
        self.focus_areas = profile.focus_areas
        self.field_conventions = profile.field_conventions
        self.sql_rules = profile.sql_rules
        self.answer_rules = profile.answer_rules
        self.default_tables = profile.default_tables
        self.helper_tables = profile.helper_tables
        self.keyword_table_map = profile.keyword_table_map

    def _check_cancellation(self, config: dict | None) -> None:
        if config and config.get("is_cancelled") and config["is_cancelled"]():
            raise CancelledError("Workflow cancelled")

    def plan(self, decision: RouteDecision) -> SkillPlan:
        tables = self._resolve_tables(decision)
        return SkillPlan(
            skill_name=self.skill_name,
            domain=self.domain,
            node_name=self.node_name,
            tables=tables,
            reason=decision.reason or f"matched {self.domain} domain",
        )

    def prepare_state(
        self,
        *,
        question: str,
        chat_history: list[str],
        decision: RouteDecision,
    ) -> dict[str, Any]:
        return self._initial_state(question, chat_history, decision)

    def apply_guard(self, state: dict[str, Any], config: dict | None = None) -> dict[str, Any]:
        self._check_cancellation(config)
        decision = llm_complete(
            build_guard_prompt(
                domain_label=self.domain_label or self.domain,
                guard_scope=self.guard_scope or (self.domain_label or self.domain),
                question=state["question"],
            ),
            task="guard"
        )
        if "REJECT" in decision:
            return {"intent": "REJECT"}
        return {"intent": state["intent"]}

    def apply_refine_filters(self, state: dict[str, Any]) -> dict[str, Any]:
        question = state.get("normalized_question") or state["question"]
        intent = state.get("intent") or ""
        refined_filters = apply_filter_refinement(
            question=question,
            intent=intent,
            filters=state.get("intent_filters") or {},
            allowed_tables=self._allowed_tables(),
        )
        return {"refined_filters": refined_filters}

    def apply_schema(self, state: dict[str, Any], *, question: str, plan: SkillPlan) -> dict[str, Any]:
        primary_table = self._primary_table(question, plan.tables, state.get("refined_filters") or {})
        refined_filters = dict(state.get("refined_filters") or {})
        refined_filters["table"] = primary_table
        return {
            "refined_filters": refined_filters,
            "table_schema": build_schema_excerpt(self._schema_tables(primary_table, plan.tables)),
        }

    def apply_write_sql(self, state: dict[str, Any], config: dict | None = None) -> dict[str, Any]:
        self._check_cancellation(config)
        history_list = state.get("chat_history", [])
        history_text = "\n".join(history_list) if history_list else ""
        effective_question = state.get("normalized_question") or state["question"]
        prompt = build_text2sql_prompt(
            domain_label=self.domain_label or self.domain,
            focus_areas=self.focus_areas,
            field_conventions=self.field_conventions,
            sql_rules=self.sql_rules,
            table_schema=state["table_schema"],
            question=f"【前情提要】\n{history_text}\n\n【当前用户问题】\n{effective_question}" if history_text else effective_question,
            structured_filters=state.get("refined_filters") or {},
        )

        strategy_hints = (
            "优先单表和最小必要字段，先保证条件正确。",
            "优先清晰聚合口径，必要时再使用 JOIN。",
        )
        allowed_tables = self._allowed_tables()
        filters = state.get("refined_filters") or {}

        def _normalize_sql(raw_sql: str) -> str:
            return harden_sql(
                sanitize_sql(raw_sql),
                structured_filters=filters,
                question=effective_question,
                domain=self.domain,
                allowed_tables=allowed_tables,
            )

        sql_candidates: list[str] = [_normalize_sql(llm_complete(prompt, stream=True, task="sql"))]
        ranking = choose_best_sql_candidate(
            sql_candidates,
            question=effective_question,
            domain=self.domain,
            structured_filters=filters,
            allowed_tables=allowed_tables,
        )

        if SQL_CANDIDATE_COUNT > 1 and self._should_expand_sql_candidates(ranking):
            for hint in strategy_hints[: max(0, SQL_CANDIDATE_COUNT - 1)]:
                alt_prompt = f"{prompt}\n\n补充要求：请给出另一种 SQL 写法，{hint}"
                sql_candidates.append(_normalize_sql(llm_complete(alt_prompt, stream=True, task="sql")))
                ranking = choose_best_sql_candidate(
                    sql_candidates,
                    question=effective_question,
                    domain=self.domain,
                    structured_filters=filters,
                    allowed_tables=allowed_tables,
                )
                if not self._should_expand_sql_candidates(ranking):
                    break

        sql_query = ranking.get("best_sql") or (sql_candidates[0] if sql_candidates else "")

        return {
            "sql_query": sql_query,
            "sql_candidates": sql_candidates,
            "sql_candidate_ranking": ranking.get("reports") or [],
            "retry_count": state.get("retry_count") or 0,
        }

    def _should_expand_sql_candidates(self, ranking: dict[str, Any]) -> bool:
        reports = ranking.get("reports") or []
        if not reports:
            return True
        if ranking.get("best_lint_issues"):
            return True
        if not ranking.get("best_probe_ok"):
            return True
        return int(ranking.get("best_score", -999)) < SQL_CANDIDATE_EXPAND_SCORE

    def apply_execute_sql(self, state: dict[str, Any], config: dict | None = None) -> dict[str, Any]:
        self._check_cancellation(config)
        return execute_sql(
            state.get("sql_query", ""),
            question=state.get("normalized_question") or state["question"],
            domain=self.domain,
            structured_filters=state.get("refined_filters") or {},
            allowed_tables=self._allowed_tables(),
        )

    def apply_reflect_sql(self, state: dict[str, Any], config: dict | None = None) -> dict[str, Any]:
        self._check_cancellation(config)
        prompt = build_reflect_sql_prompt(
            domain_label=self.domain_label or self.domain,
            field_conventions=self.field_conventions,
            sql_rules=self.sql_rules,
            question=state["question"],
            table_schema=state["table_schema"],
            sql_query=state["sql_query"],
            error_message=state["sql_error"],
            structured_filters=state.get("refined_filters") or {},
        )
        return {
            "sql_query": harden_sql(
                sanitize_sql(llm_complete(prompt, stream=True, task="reflect")),
                structured_filters=state.get("refined_filters") or {},
                question=state.get("normalized_question") or state["question"],
                domain=self.domain,
                allowed_tables=self._allowed_tables(),
            ),
            "retry_count": (state.get("retry_count") or 0) + 1,
            "sql_error": "",
        }

    def apply_generate_answer(self, state: dict[str, Any], config: dict | None = None) -> dict[str, Any]:
        if state.get("intent") == "REJECT":
            answer = "抱歉，我仅支持企业业务数据相关的查询与分析。请改用生产、库存、计划、需求或经营数据问题继续提问。"
            return {
                "final_answer": answer,
                "chart_data": None,
                "table_data": [],
                "table_columns": state.get("table_columns") or [],
                "row_count": state.get("row_count"),
                "truncated": bool(state.get("truncated")),
                "chat_history": [f"问: {state['question']}\n答: {answer}"],
            }
        self._check_cancellation(config)
        return build_answer_payload(
            question=state["question"],
            sql_query=state.get("sql_query", ""),
            sql_error=state.get("sql_error", ""),
            db_result=state.get("db_result") or [],
            columns=state.get("table_columns") or [],
            row_count=state.get("row_count"),
            truncated=bool(state.get("truncated")),
            answer_prompt=build_answer_prompt(
                domain_label=self.domain_label or self.domain,
                answer_rules=self.answer_rules,
            ),
        )

    def _resolve_tables(self, decision: RouteDecision) -> list[str]:
        tables: list[str] = []
        for table_name in decision.target_tables:
            if table_name not in tables:
                tables.append(table_name)
        if not tables:
            tables.extend(self.default_tables)
        for helper in self.helper_tables:
            if helper not in tables:
                tables.append(helper)
        return tables

    def _allowed_tables(self) -> list[str]:
        tables = list(self.default_tables)
        for helper in self.helper_tables:
            if helper not in tables:
                tables.append(helper)
        return tables

    def _primary_table(self, question: str, tables: list[str], filters: dict[str, Any]) -> str:
        explicit = filters.get("table")
        if explicit and explicit in tables:
            return explicit

        q = question.lower()
        for tokens, table_name in self.keyword_table_map:
            if any(token.lower() in q for token in tokens) and table_name in tables:
                return table_name

        for table_name in tables:
            if table_name not in self.helper_tables:
                return table_name
        return tables[0]

    def _schema_tables(self, primary_table: str, planned_tables: list[str]) -> list[str]:
        tables = [primary_table]
        for table_name in planned_tables:
            if table_name not in tables:
                tables.append(table_name)
        return tables

    def _initial_state(
        self,
        question: str,
        chat_history: list[str],
        decision: RouteDecision,
    ) -> dict[str, Any]:
        normalized_question = (
            decision.filters.get("_normalized_question")
            if isinstance(decision.filters, dict)
            else None
        ) or question
        return {
            "question": question,
            "chat_history": list(chat_history or []),
            "table_schema": "",
            "normalized_question": normalized_question,
            "lexicon_hits": [],
            "intent": decision.intent or f"{self.domain}_query",
            "intent_confidence": decision.confidence,
            "intent_filters": dict(decision.filters or {}),
            "refined_filters": {},
            "sql_query": "",
            "sql_candidates": [],
            "sql_candidate_ranking": [],
            "sql_error": "",
            "db_result": [],
            "final_answer": "",
            "retry_count": 0,
            "chart_data": None,
            "table_data": [],
            "table_columns": [],
            "row_count": None,
            "truncated": False,
        }

    def _build_result(self, state: dict[str, Any]) -> SkillResult:
        return SkillResult(
            skill_name=self.skill_name,
            final_answer=state.get("final_answer", ""),
            sql_query=state.get("sql_query", ""),
            sql_error=state.get("sql_error", ""),
            db_result=state.get("db_result") or [],
            table_columns=state.get("table_columns") or [],
            table_data=state.get("table_data"),
            chart_data=state.get("chart_data"),
            row_count=state.get("row_count"),
            truncated=bool(state.get("truncated")),
            chat_history=state.get("chat_history") or [],
        )

    def build_result(self, state: dict[str, Any]) -> SkillResult:
        return self._build_result(state)
