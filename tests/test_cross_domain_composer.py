import unittest

from core.composer.cross_domain import CrossDomainComposer
from core.runtime.state import RouteDecision, SkillExecution, SkillPlan, SkillResult


class CrossDomainComposerTestCase(unittest.TestCase):
    def test_compose_into_sequential_skill_plans(self):
        composer = CrossDomainComposer()
        decision = RouteDecision(
            route="cross_domain",
            matched_domains=["inventory", "planning"],
            target_tables=["daily_inventory", "daily_PLAN", "monthly_plan_approved"],
        )

        result = composer.compose(decision)

        self.assertFalse(result.use_legacy_fallback)
        self.assertEqual(result.execution_order, ["inventory", "planning"])
        self.assertIn("daily_inventory", result.domain_tables["inventory"])
        self.assertIn("库存域", result.domain_questions["inventory"])

    def test_merge_skill_results(self):
        composer = CrossDomainComposer()
        inventory_execution = SkillExecution(
            domain="inventory",
            plan=SkillPlan(skill_name="inventory_skill", domain="inventory", node_name="inventory_skill"),
            result=SkillResult(
                skill_name="inventory_skill",
                final_answer="库存域返回了 12 条结果。",
                sql_query="select * from daily_inventory",
                db_result=[["P1", 10]],
                table_columns=["product_ID", "TTL_Qty"],
                row_count=12,
            ),
        )
        planning_execution = SkillExecution(
            domain="planning",
            plan=SkillPlan(skill_name="planning_skill", domain="planning", node_name="planning_skill"),
            result=SkillResult(
                skill_name="planning_skill",
                final_answer="计划域返回了 4 条结果。",
                sql_query="select * from daily_PLAN",
                db_result=[["P1", 8]],
                table_columns=["product_ID", "target_qty"],
                row_count=4,
            ),
        )

        merge_result = composer.merge("结合库存和排产分析风险", [inventory_execution, planning_execution])

        self.assertEqual(merge_result.execution_order, ["inventory", "planning"])
        self.assertEqual(merge_result.successful_domains, ["inventory", "planning"])
        self.assertEqual(merge_result.final_result.table_columns[0], "domain")
        self.assertEqual(merge_result.final_result.row_count, 2)
        self.assertIn("库存域", merge_result.final_result.final_answer)


if __name__ == "__main__":
    unittest.main()
