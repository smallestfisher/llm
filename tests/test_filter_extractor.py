import unittest

from core.router.filter_extractor import extract_shared_filters
from core.router.intent_router import route_question


class FilterExtractorTestCase(unittest.TestCase):
    def test_extract_recent_days_and_latest(self):
        filters = extract_shared_filters("查询最近7天最新库存情况")
        self.assertEqual(filters.get("recent_days"), 7)
        self.assertTrue(filters.get("latest"))

    def test_extract_date_range(self):
        filters = extract_shared_filters("查询 2025-01-01 到 2025-01-31 的排产数据")
        self.assertEqual(filters.get("date_from"), "2025-01-01")
        self.assertEqual(filters.get("date_to"), "2025-01-31")

    def test_router_carries_shared_filters(self):
        decision = route_question("查询最近14天库存风险")
        self.assertEqual(decision.route, "inventory")
        self.assertEqual(decision.filters.get("recent_days"), 14)


if __name__ == "__main__":
    unittest.main()
