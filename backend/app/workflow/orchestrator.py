from __future__ import annotations

from app.workflow.composer import CrossDomainComposer
from app.workflow.router import route_question
from app.workflow.state import RouteDecision, SkillExecution
from app.skills.demand import DemandSkill
from app.skills.generic import GenericSkill
from app.skills.inventory import InventorySkill
from app.skills.planning import PlanningSkill
from app.skills.production import ProductionSkill
from app.skills.sales import SalesSkill


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

    async def astream(self, inputs: dict, config: dict | None = None):
        question = (inputs.get("question") or "").strip()
        chat_history = list(inputs.get("chat_history") or [])
        decision = route_question(question)

        yield {"route_intent": decision.to_state_update()}

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
            ):
                yield output
            return

        if decision.route == "cross_domain":
            compose_result = _COMPOSER.compose(decision)
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
            executions: list[SkillExecution] = []
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
                holder: dict = {}
                async for output in self._execute_skill_astream(
                    skill=skill,
                    plan=plan,
                    question=question,
                    chat_history=chat_history,
                    decision=subdecision,
                    result_holder=holder,
                    emit_final_node=False,
                    dispatch_update={
                        **plan.to_state_update(),
                        "cross_domain": True,
                        "skill_index": index,
                        "skill_total": len(compose_result.execution_order),
                    },
                ):
                    yield output
                result = holder.get("result")
                if result is not None:
                    executions.append(SkillExecution(domain=domain, plan=plan, result=result))
            merge_result = _COMPOSER.merge(question, executions)
            yield {"cross_domain_merge": merge_result.to_state_update()}
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
    ):
        yield {"skill_dispatch": dispatch_update or plan.to_state_update()}
        yield {plan.node_name: {"active_skill": plan.skill_name, "skill_tables": plan.tables}}

        state = skill.prepare_state(
            question=question,
            chat_history=chat_history,
            decision=decision,
        )

        yield {"check_guard": {}}
        guard_update = skill.apply_guard(state)
        state.update(guard_update)
        yield {"check_guard": guard_update}

        if state.get("intent") == "REJECT":
            if emit_final_node:
                yield {"generate_answer": {}}
            final_update = skill.apply_generate_answer(state)
            state.update(final_update)
            result = skill.build_result(state)
            yield {plan.node_name: result.to_skill_update()}
            if emit_final_node:
                yield {"generate_answer": final_update}
            result_holder["state"] = state
            result_holder["result"] = result
            return

        yield {"refine_filters": {}}
        refine_update = skill.apply_refine_filters(state)
        state.update(refine_update)
        yield {"refine_filters": refine_update}

        yield {"get_schema": {}}
        schema_update = skill.apply_schema(state, question=question, plan=plan)
        state.update(schema_update)
        yield {"get_schema": schema_update}

        yield {"write_sql": {}}
        write_update = skill.apply_write_sql(state)
        state.update(write_update)
        yield {"write_sql": write_update}

        while True:
            yield {"execute_sql": {}}
            execute_update = skill.apply_execute_sql(state)
            state.update(execute_update)
            yield {"execute_sql": execute_update}
            if not state.get("sql_error") or (state.get("retry_count") or 0) >= 3:
                break
            yield {"reflect_sql": {}}
            reflect_update = skill.apply_reflect_sql(state)
            state.update(reflect_update)
            yield {"reflect_sql": reflect_update}

        if emit_final_node:
            yield {"generate_answer": {}}
        final_update = skill.apply_generate_answer(state)
        state.update(final_update)
        result = skill.build_result(state)
        yield {plan.node_name: result.to_skill_update()}
        if emit_final_node:
            yield {"generate_answer": final_update}
        result_holder["state"] = state
        result_holder["result"] = result


class OrchestratedWorkflow:
    def compile(self, checkpointer=None):
        return CompiledOrchestratedWorkflow(checkpointer=checkpointer)


def get_workflow():
    return OrchestratedWorkflow()


async def get_compiled_workflow():
    return get_workflow().compile()
