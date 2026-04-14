from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.semantic.domains import get_tables_for_domain
from app.workflow.state import RouteDecision, SkillExecution, SkillResult


@dataclass(slots=True)
class CrossDomainComposeResult:
    use_legacy_fallback: bool
    domains: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    execution_order: list[str] = field(default_factory=list)
    domain_tables: dict[str, list[str]] = field(default_factory=dict)
    domain_questions: dict[str, str] = field(default_factory=dict)
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_state_update(self) -> dict[str, Any]:
        payload = {
            "cross_domain": bool(self.domains),
            "cross_domain_domains": self.domains,
            "cross_domain_tables": self.tables,
            "cross_domain_execution_order": self.execution_order,
            "cross_domain_reason": self.reason,
            "cross_domain_questions": self.domain_questions,
            "use_legacy_fallback": self.use_legacy_fallback,
        }
        payload.update(self.metadata)
        return payload


@dataclass(slots=True)
class CrossDomainMergeResult:
    final_result: SkillResult
    execution_order: list[str] = field(default_factory=list)
    successful_domains: list[str] = field(default_factory=list)
    failed_domains: list[str] = field(default_factory=list)

    def to_state_update(self) -> dict[str, Any]:
        return {
            "cross_domain_execution_order": self.execution_order,
            "cross_domain_successful_domains": self.successful_domains,
            "cross_domain_failed_domains": self.failed_domains,
            "cross_domain_skill_count": len(self.execution_order),
        }


class CrossDomainComposer:
    def compose(self, decision: RouteDecision) -> CrossDomainComposeResult:
        execution_order: list[str] = []
        domain_tables: dict[str, list[str]] = {}
        domain_questions: dict[str, str] = {}
        for domain in decision.matched_domains:
            if domain not in execution_order:
                execution_order.append(domain)
            available_tables = get_tables_for_domain(domain)
            selected = [table for table in decision.target_tables if table in available_tables]
            domain_tables[domain] = selected
            domain_questions[domain] = self._build_domain_question(domain=domain, original_question="")

        if not execution_order:
            return CrossDomainComposeResult(
                use_legacy_fallback=True,
                domains=list(decision.matched_domains),
                tables=list(decision.target_tables),
                reason="no concrete domains available for cross-domain composition",
                metadata={"next_phase": "expand route hints before composing"},
            )

        return CrossDomainComposeResult(
            use_legacy_fallback=False,
            domains=list(decision.matched_domains),
            tables=list(decision.target_tables),
            execution_order=execution_order,
            domain_tables=domain_tables,
            domain_questions=domain_questions,
            reason="decomposed into sequential domain skill plans",
            metadata={"compose_mode": "sequential_skills"},
        )

    def build_domain_question(self, domain: str, original_question: str) -> str:
        return self._build_domain_question(domain=domain, original_question=original_question)

    def merge(self, question: str, executions: list[SkillExecution]) -> CrossDomainMergeResult:
        successful_domains: list[str] = []
        failed_domains: list[str] = []
        rows: list[list[Any]] = []
        answer_lines = ["已完成跨域编排查询，以下为各域执行结果概览。"]
        sql_blocks: list[str] = []

        for execution in executions:
            domain = execution.domain
            result = execution.result
            row_count = result.row_count if result.row_count is not None else len(result.db_result)
            status = "failed" if result.sql_error else "ok"
            if result.sql_error:
                failed_domains.append(domain)
                summary = f"{self._domain_label(domain)}查询失败：{result.sql_error}"
            else:
                successful_domains.append(domain)
                snippet = self._compact_text(result.final_answer)
                summary = f"{self._domain_label(domain)}查询完成，共得到 {row_count} 条记录。{snippet}"
            answer_lines.append(f"- {summary}")
            rows.append([domain, status, row_count, "yes" if result.truncated else "no", result.sql_query])
            if result.sql_query:
                sql_blocks.append(f"-- {domain}\n{result.sql_query}")

        if successful_domains and failed_domains:
            answer_lines.append("部分域已返回结果，部分域执行失败。后续可继续细化产品、工厂或时间范围。")
        elif not successful_domains:
            answer_lines.append("当前各域都未得到可用结果，建议先收窄查询范围后重试。")
        else:
            answer_lines.append("如需更精细的业务结论，可继续限定产品、工厂、客户或时间窗口。")

        final_answer = "\n".join(answer_lines)
        final_result = SkillResult(
            skill_name="cross_domain_merge",
            final_answer=final_answer,
            sql_query="\n\n".join(sql_blocks),
            db_result=rows,
            table_columns=["domain", "status", "row_count", "truncated", "sql_query"],
            table_data=rows,
            row_count=len(rows),
            truncated=False,
            chat_history=[f"问: {question}\n答: {final_answer}"],
        )
        return CrossDomainMergeResult(
            final_result=final_result,
            execution_order=[execution.domain for execution in executions],
            successful_domains=successful_domains,
            failed_domains=failed_domains,
        )

    def _domain_label(self, domain: str) -> str:
        labels = {
            "inventory": "库存域",
            "production": "生产域",
            "planning": "计划域",
            "demand": "需求域",
            "sales": "销售财务域",
        }
        return labels.get(domain, domain)

    def _compact_text(self, text: str) -> str:
        line = " ".join((text or "").strip().splitlines())
        if not line:
            return ""
        return line[:120] + ("..." if len(line) > 120 else "")

    def _build_domain_question(self, *, domain: str, original_question: str) -> str:
        task_lines = {
            "inventory": (
                "仅提取库存侧事实，关注 TTL/HOLD/OMS/库龄/客户仓，不做计划差异或需求覆盖判断。",
                "如果原问题涉及支撑、缺料、影响，只返回库存基础量和风险线索，不自行推导计划值。",
            ),
            "planning": (
                "仅提取计划侧事实，关注日排产、周滚计划、审批版月计划。",
                "不要把 daily_PLAN 当实际产出，不要把 production_actuals 的实际结果或销售结果映射到计划表。",
            ),
            "production": (
                "仅提取生产实绩侧事实，关注投入、产出、报废、不良。",
                "不要用计划表替代实际，不要回答库存覆盖、需求承诺或销售财务口径。",
            ),
            "demand": (
                "仅提取需求与承诺侧事实，关注 V版 forecast、P版 commit 与横表月份列。",
                "V版/P版优先决定使用哪张表，不要把“V版”或“P版”误当成 PM_VERSION 的字面值。",
            ),
            "sales": (
                "仅提取销售财务侧事实，关注 sales_qty 和 FINANCIAL_qty。",
                "不要虚构 sales_actual、revenue、gross_margin 等不存在的表或字段，也不要替用户做计划对比。",
            ),
        }.get(domain, ("仅提取当前业务域可直接回答的事实。",))
        bullet_text = "\n".join(f"- {line}" for line in task_lines)
        return (
            f"原始问题：{original_question}\n"
            f"当前是跨域拆解中的 {self._domain_label(domain)} 子任务。\n"
            "请严格只回答当前域可直接查询的事实，不要跨到其他域补字段、补表或补结论。\n"
            f"{bullet_text}"
        )
