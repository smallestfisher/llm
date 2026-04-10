import unittest

from core.composer.cross_domain import CrossDomainComposer
from core.runtime.state import RouteDecision, SkillExecution, SkillPlan, SkillResult


class CrossDomainComposerTestCase(unittest.TestCase):
    def test_compose_into_sequential_skill_plans(self):
        composer = CrossDomainComposer()
        decision = RouteDecision(
            route="cross_domain",
            matched_domains=["inventory", "production"],
            target_tables=["daily_inventory", "daily_schedule", "work_in_progress"],
        )

        result = composer.compose(decision)

        self.assertFalse(result.use_legacy_fallback)
        self.assertEqual(result.execution_order, ["inventory", "production"])
        self.assertIn("daily_inventory", result.domain_tables["inventory"])

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
                table_columns=["product_code", "available_qty"],
                row_count=12,
            ),
        )
        production_execution = SkillExecution(
            domain="production",
            plan=SkillPlan(skill_name="production_skill", domain="production", node_name="production_skill"),
            result=SkillResult(
                skill_name="production_skill",
                final_answer="生产域返回了 4 条结果。",
                sql_query="select * from daily_schedule",
                db_result=[["P1", 8]],
                table_columns=["product_code", "target_qty"],
                row_count=4,
            ),
        )

        merge_result = composer.merge("结合库存和排产分析风险", [inventory_execution, production_execution])

        self.assertEqual(merge_result.execution_order, ["inventory", "production"])
        self.assertEqual(merge_result.successful_domains, ["inventory", "production"])
        self.assertEqual(merge_result.final_result.table_columns[0], "domain")
        self.assertEqual(merge_result.final_result.row_count, 2)
        self.assertIn("库存域", merge_result.final_result.final_answer)


if __name__ == "__main__":
    unittest.main()
