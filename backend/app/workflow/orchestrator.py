from __future__ import annotations

import asyncio
import os

from app.workflow.composer import CrossDomainComposer
from app.workflow.router import route_question
from app.workflow.state import RouteDecision, SkillExecution, SkillResult, CancelledError
from app.skills.demand import DemandSkill
from app.skills.generic import GenericSkill
from app.skills.inventory import InventorySkill
from app.skills.planning import PlanningSkill
from app.skills.production import ProductionSkill
from app.skills.sales import SalesSkill


from app.logging_config import get_logger

logger = get_logger(__name__)
CROSS_DOMAIN_MAX_PARALLEL = max(1, int(os.getenv("CROSS_DOMAIN_MAX_PARALLEL", "2")))



_COMPOSER = CrossDomainComposer()
_SKILLS = {
    "general": GenericSkill(),
    "production": ProductionSkill(),
    "planning": PlanningSkill(),
    "inventory": InventorySkill(),
    "demand": DemandSkill(),
    "sales": SalesSkill(),
}


class CompiledOrchestratedWorkflow:
    def __init__(self, checkpointer=None):
        self.checkpointer = checkpointer

    def _check_cancellation(self, config: dict | None) -> None:
        if config and config.get("is_cancelled") and config["is_cancelled"]():
            raise CancelledError("Workflow cancelled")

    async def astream(self, inputs: dict, config: dict | None = None):
        self._check_cancellation(config)
        question = (inputs.get("question") or "").strip()
        chat_history = list(inputs.get("chat_history") or [])
        decision = inputs.get("initial_decision") or route_question(question)
        logger.info(f"decision: {decision}")
        self._emit_event(config, "route_intent", decision.to_state_update())
        yield {"route_intent": decision.to_state_update()}
        self._check_cancellation(config)

        if decision.route == "legacy":

            generic_decision = RouteDecision(
                route="general",
                confidence=decision.confidence,
                matched_domains=decision.matched_domains,
                target_tables=decision.target_tables,
                filters=dict(decision.filters or {}),
                reason=decision.reason,
                intent=decision.intent,
            )
            generic_skill = _SKILLS["general"]
            generic_plan = generic_skill.plan(generic_decision)
            async for output in self._execute_skill_astream(
                skill=generic_skill,
                plan=generic_plan,
                question=question,
                chat_history=chat_history,
                decision=generic_decision,
                result_holder={},
                emit_final_node=True,
                config=config,
            ):
                yield output
            return

        if decision.route == "cross_domain":
            compose_result = _COMPOSER.compose(decision)
            self._emit_event(config, "cross_domain_compose", compose_result.to_state_update())
            yield {"cross_domain_compose": compose_result.to_state_update()}
            if compose_result.use_legacy_fallback:
                generic_decision = RouteDecision(
                    route="general",
                    confidence=decision.confidence,
                    matched_domains=decision.matched_domains,
                    target_tables=decision.target_tables,
                    filters=dict(decision.filters or {}),
                    reason="cross-domain composer fallback to generic skill",
                    intent=decision.intent,
                )
                generic_skill = _SKILLS["general"]
                generic_plan = generic_skill.plan(generic_decision)
                async for output in self._execute_skill_astream(
                    skill=generic_skill,
                    plan=generic_plan,
                    question=question,
                    chat_history=chat_history,
                    decision=generic_decision,
                    result_holder={},
                    emit_final_node=True,
                ):
                    yield output
                return
            jobs: list[tuple[int, str, object, object, RouteDecision, dict]] = []
            for index, domain in enumerate(compose_result.execution_order, start=1):
                skill = _SKILLS.get(domain)
                if skill is None:
                    continue
                domain_question = _COMPOSER.build_domain_question(domain, question)
                subdecision = RouteDecision(
                    route=domain,
                    confidence=decision.confidence,
                    matched_domains=[domain],
                    target_tables=compose_result.domain_tables.get(domain, []),
                    filters={
                        **dict(decision.filters or {}),
                        "_normalized_question": domain_question,
                        "_cross_domain": True,
                        "_cross_domain_parent_question": question,
                    },
                    reason=f"cross-domain step {index}/{len(compose_result.execution_order)}",
                    intent=decision.intent,
                )
                plan = skill.plan(subdecision)
                dispatch_update = {
                    **plan.to_state_update(),
                    "cross_domain": True,
                    "skill_index": index,
                    "skill_total": len(compose_result.execution_order),
                }
                jobs.append((index, domain, skill, plan, subdecision, dispatch_update))

            executions: list[SkillExecution] = []
            for _, _, skill, plan, _, dispatch_update in jobs:
                self._check_cancellation(config)
                yield {"skill_dispatch": dispatch_update}
                self._emit_event(config, "skill_dispatch", dispatch_update)
                active_update = {"active_skill": plan.skill_name, "skill_tables": plan.tables}
                yield {plan.node_name: active_update}
                self._emit_event(config, plan.node_name, active_update)

            parallel_config = self._parallel_config(config)
            if len(jobs) > 1 and CROSS_DOMAIN_MAX_PARALLEL > 1:
                semaphore = asyncio.Semaphore(CROSS_DOMAIN_MAX_PARALLEL)

                async def _run_job(skill, plan, subdecision):
                    async with semaphore:
                        return await asyncio.to_thread(
                            self._execute_skill_once,
                            skill=skill,
                            plan=plan,
                            question=question,
                            chat_history=chat_history,
                            decision=subdecision,
                            config=parallel_config,
                        )

                tasks = [_run_job(skill, plan, subdecision) for _, _, skill, plan, subdecision, _ in jobs]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for (_, domain, _, plan, _, _), result in zip(jobs, results):
                    self._check_cancellation(config)
                    if isinstance(result, Exception):
                        logger.bind(domain=domain).error("cross domain skill execution failed: {}", result)
                        skill_result = self._build_skill_error_result(plan, domain, str(result))
                    else:
                        skill_result = result
                    executions.append(SkillExecution(domain=domain, plan=plan, result=skill_result))
                    update = skill_result.to_skill_update()
                    yield {plan.node_name: update}
                    self._emit_event(config, plan.node_name, update)
            else:
                for _, domain, skill, plan, subdecision, _ in jobs:
                    self._check_cancellation(config)
                    try:
                        result = self._execute_skill_once(
                            skill=skill,
                            plan=plan,
                            question=question,
                            chat_history=chat_history,
                            decision=subdecision,
                            config=parallel_config,
                        )
                    except Exception as exc:
                        logger.bind(domain=domain).exception("cross domain skill execution failed")
                        result = self._build_skill_error_result(plan, domain, str(exc))
                    executions.append(SkillExecution(domain=domain, plan=plan, result=result))
                    update = result.to_skill_update()
                    yield {plan.node_name: update}
                    self._emit_event(config, plan.node_name, update)
            merge_result = _COMPOSER.merge(question, executions)
            self._emit_event(config, "cross_domain_merge", merge_result.to_state_update())
            yield {"cross_domain_merge": merge_result.to_state_update()}
            self._emit_event(config, "generate_answer", merge_result.final_result.to_final_update())
            yield {"generate_answer": merge_result.final_result.to_final_update()}
            return

        skill = _SKILLS.get(decision.route)
        if skill is None:
            generic_decision = RouteDecision(
                route="general",
                confidence=decision.confidence,
                matched_domains=decision.matched_domains,
                target_tables=decision.target_tables,
                filters=dict(decision.filters or {}),
                reason=f"unknown route {decision.route}, fallback to generic skill",
                intent=decision.intent,
            )
            generic_skill = _SKILLS["general"]
            generic_plan = generic_skill.plan(generic_decision)
            async for output in self._execute_skill_astream(
                skill=generic_skill,
                plan=generic_plan,
                question=question,
                chat_history=chat_history,
                decision=generic_decision,
                result_holder={},
                emit_final_node=True,
                config=config,
            ):
                yield output
            return

        plan = skill.plan(decision)
        async for output in self._execute_skill_astream(
            skill=skill,
            plan=plan,
            question=question,
            chat_history=chat_history,
            decision=decision,
            result_holder={},
            emit_final_node=True,
        ):
            yield output

    async def ainvoke(self, inputs: dict, config: dict | None = None):
        state: dict = {}
        async for output in self.astream(inputs, config=config):
            for node_output in output.values():
                if isinstance(node_output, dict):
                    state.update(node_output)
        return state

    async def _execute_skill_astream(
        self,
        *,
        skill,
        plan,
        question: str,
        chat_history: list[str],
        decision: RouteDecision,
        result_holder: dict,
        emit_final_node: bool,
        dispatch_update: dict | None = None,
        config: dict | None = None,
    ):
        self._check_cancellation(config)
        yield {"skill_dispatch": dispatch_update or plan.to_state_update()}
        self._emit_event(config, "skill_dispatch", dispatch_update or plan.to_state_update())
        yield {plan.node_name: {"active_skill": plan.skill_name, "skill_tables": plan.tables}}
        self._emit_event(config, plan.node_name, {"active_skill": plan.skill_name, "skill_tables": plan.tables})

        state = skill.prepare_state(
            question=question,
            chat_history=chat_history,
            decision=decision,
        )

        self._check_cancellation(config)
        yield {"check_guard": {}}
        self._emit_event(config, "check_guard", {})
        guard_update = skill.apply_guard(state, config=config)
        state.update(guard_update)
        yield {"check_guard": guard_update}
        self._emit_event(config, "check_guard", guard_update)

        if state.get("intent") == "REJECT":
            if emit_final_node:
                yield {"generate_answer": {}}
                self._emit_event(config, "generate_answer", {})
            self._check_cancellation(config)
            final_update = skill.apply_generate_answer(state, config=config)
            state.update(final_update)
            result = skill.build_result(state)
            yield {plan.node_name: result.to_skill_update()}
            self._emit_event(config, plan.node_name, result.to_skill_update())
            if emit_final_node:
                yield {"generate_answer": final_update}
                self._emit_event(config, "generate_answer", final_update)
            result_holder["state"] = state
            result_holder["result"] = result
            return

        self._check_cancellation(config)
        yield {"refine_filters": {}}
        self._emit_event(config, "refine_filters", {})
        refine_update = skill.apply_refine_filters(state)
        state.update(refine_update)
        yield {"refine_filters": refine_update}
        self._emit_event(config, "refine_filters", refine_update)

        self._check_cancellation(config)
        yield {"get_schema": {}}
        self._emit_event(config, "get_schema", {})
        schema_update = skill.apply_schema(state, question=question, plan=plan)
        state.update(schema_update)
        yield {"get_schema": schema_update}
        self._emit_event(config, "get_schema", schema_update)

        self._check_cancellation(config)
        yield {"write_sql": {}}
        self._emit_event(config, "write_sql", {})
        write_update = skill.apply_write_sql(state, config=config)
        state.update(write_update)
        yield {"write_sql": write_update}
        self._emit_event(config, "write_sql", write_update)

        while True:
            self._check_cancellation(config)
            yield {"execute_sql": {}}
            self._emit_event(config, "execute_sql", {})
            execute_update = skill.apply_execute_sql(state, config=config)
            state.update(execute_update)
            yield {"execute_sql": execute_update}
            self._emit_event(config, "execute_sql", execute_update)
            if not state.get("sql_error") or (state.get("retry_count") or 0) >= 3:
                break
            
            self._check_cancellation(config)
            yield {"reflect_sql": {}}
            self._emit_event(config, "reflect_sql", {})
            reflect_update = skill.apply_reflect_sql(state, config=config)
            state.update(reflect_update)
            yield {"reflect_sql": reflect_update}
            self._emit_event(config, "reflect_sql", reflect_update)

        self._check_cancellation(config)
        if emit_final_node:
            yield {"generate_answer": {}}
            self._emit_event(config, "generate_answer", {})
        final_update = skill.apply_generate_answer(state, config=config)
        state.update(final_update)
        result = skill.build_result(state)
        yield {plan.node_name: result.to_skill_update()}
        self._emit_event(config, plan.node_name, result.to_skill_update())
        if emit_final_node:
            yield {"generate_answer": final_update}
            self._emit_event(config, "generate_answer", final_update)
        result_holder["state"] = state
        result_holder["result"] = result

    def _emit_event(self, config: dict | None, node: str, payload: dict) -> None:
        if not config:
            return
        callback = config.get("on_event")
        if callback:
            callback(node, payload)

    def _parallel_config(self, config: dict | None) -> dict | None:
        if not config:
            return None
        is_cancelled = config.get("is_cancelled")
        if not is_cancelled:
            return None
        return {"is_cancelled": is_cancelled}

    def _build_skill_error_result(self, plan, domain: str, error_message: str) -> SkillResult:
        answer = f"{domain} 域执行失败: {error_message}"
        return SkillResult(
            skill_name=plan.skill_name,
            final_answer=answer,
            sql_query="",
            sql_error=error_message,
            db_result=[],
            table_columns=[],
            table_data=[],
            chart_data=None,
            row_count=0,
            truncated=False,
            chat_history=[answer],
        )

    def _execute_skill_once(
        self,
        *,
        skill,
        plan,
        question: str,
        chat_history: list[str],
        decision: RouteDecision,
        config: dict | None = None,
    ) -> SkillResult:
        self._check_cancellation(config)
        state = skill.prepare_state(
            question=question,
            chat_history=chat_history,
            decision=decision,
        )
        state.update(skill.apply_guard(state, config=config))
        if state.get("intent") == "REJECT":
            state.update(skill.apply_generate_answer(state, config=config))
            return skill.build_result(state)

        state.update(skill.apply_refine_filters(state))
        state.update(skill.apply_schema(state, question=question, plan=plan))
        state.update(skill.apply_write_sql(state, config=config))

        while True:
            self._check_cancellation(config)
            state.update(skill.apply_execute_sql(state, config=config))
            if not state.get("sql_error") or (state.get("retry_count") or 0) >= 3:
                break
            state.update(skill.apply_reflect_sql(state, config=config))

        state.update(skill.apply_generate_answer(state, config=config))
        return skill.build_result(state)


class OrchestratedWorkflow:
    def compile(self, checkpointer=None):
        return CompiledOrchestratedWorkflow(checkpointer=checkpointer)


def get_workflow():
    return OrchestratedWorkflow()


async def get_compiled_workflow():
    return get_workflow().compile()
