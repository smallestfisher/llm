import unittest

from app.semantic.filters import extract_shared_filters
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

    def test_extract_compact_month_and_full_pm_version(self):
        filters = extract_shared_filters("最新四版需求，202604月P版需求最大的FGCODE是哪个，版本202604W1P1")
        self.assertEqual(filters.get("month"), "2026-04")
        self.assertEqual(filters.get("PM_VERSION"), "202604W1P1")

    def test_extract_relative_month_and_week(self):
        filters = extract_shared_filters("看下本月销量和下周排产")
        self.assertEqual(filters.get("relative_month"), "current_month")
        self.assertEqual(filters.get("relative_week"), "next_week")

    def test_extract_relative_day(self):
        filters = extract_shared_filters("昨天的报废实绩")
        self.assertEqual(filters.get("relative_day"), "yesterday")

    def test_router_carries_shared_filters(self):
        decision = route_question("查询最近14天库存风险")
        self.assertEqual(decision.route, "inventory")
        self.assertEqual(decision.filters.get("recent_days"), 14)


if __name__ == "__main__":
    unittest.main()
