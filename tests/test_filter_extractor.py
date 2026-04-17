import unittest
from datetime import date
from unittest import mock

from app.semantic.filters import apply_filter_refinement, extract_shared_filters
from app import workflow as workflow_pkg
from app.workflow.router import route_question


class FilterExtractorTestCase(unittest.TestCase):
    def test_extract_recent_days_and_latest(self):
        filters = extract_shared_filters("查询最近7天最新库存情况")
        self.assertEqual(filters.get("recent_days"), 7)
        self.assertTrue(filters.get("latest"))

    def test_extract_date_range(self):
        filters = extract_shared_filters("查询 2025-01-01 到 2025-01-31 的排产数据")
        self.assertEqual(filters.get("date_from"), "2025-01-01")
        self.assertEqual(filters.get("date_to"), "2025-01-31")

    def test_extract_version_and_factory(self):
        filters = extract_shared_filters("查看2026W03版本 B4_BJ 工厂周计划")
        self.assertEqual(filters.get("PM_VERSION"), "2026W03")
        self.assertEqual(filters.get("factory"), "B4_BJ")

    def test_extract_relative_month_and_week(self):
        filters = extract_shared_filters("看下本月销量和下周排产")
        self.assertEqual(filters.get("relative_month"), "current_month")
        self.assertEqual(filters.get("relative_week"), "next_week")

    def test_extract_relative_day(self):
        filters = extract_shared_filters("昨天的报废实绩")
        self.assertEqual(filters.get("relative_day"), "yesterday")

    def test_router_carries_shared_filters(self):
        with mock.patch.object(workflow_pkg.router, "_llm_route_question", return_value=None):
            decision = route_question("查询最近14天库存风险")
        self.assertEqual(decision.route, "inventory")
        self.assertEqual(decision.filters.get("recent_days"), 14)

    def test_refine_demand_week_prefix_for_p_table(self):
        refined = apply_filter_refinement(
            question="看下2026年4月第三周P版承诺需求",
            intent="demand_query",
            filters={},
            allowed_tables=["p_demand", "product_attributes", "product_mapping"],
        )
        self.assertEqual(refined.get("pm_version_prefix"), "202604W3")
        self.assertEqual(refined.get("pm_version_table_type"), "P")

    def test_refine_demand_relative_week_prefix_for_v_table(self):
        refined = apply_filter_refinement(
            question="本周V版forecast需求",
            intent="demand_query",
            filters={"relative_week": "current_week"},
            allowed_tables=["v_demand", "product_attributes", "product_mapping"],
        )
        self.assertTrue(str(refined.get("pm_version_prefix") or "").startswith(str(date.today().year)))
        self.assertEqual(refined.get("pm_version_table_type"), "V")

    def test_refine_demand_month_only_does_not_force_pm_version_prefix(self):
        refined = apply_filter_refinement(
            question="看下本月P版承诺需求",
            intent="demand_query",
            filters={"relative_month": "current_month"},
            allowed_tables=["p_demand", "product_attributes", "product_mapping"],
        )
        self.assertIsNone(refined.get("pm_version_prefix"))


if __name__ == "__main__":
    unittest.main()
