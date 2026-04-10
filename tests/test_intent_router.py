import unittest

from core.router.intent_router import route_question


class IntentRouterTestCase(unittest.TestCase):
    def test_inventory_route(self):
        decision = route_question("查询最近7天库存和在途情况")
        self.assertEqual(decision.route, "inventory")
        self.assertIn("inventory", decision.matched_domains)
        self.assertTrue(decision.target_tables)

    def test_production_route(self):
        decision = route_question("按产线看最近一周良率和停机时长")
        self.assertEqual(decision.route, "production")
        self.assertIn("production", decision.matched_domains)
        self.assertIn("production_actuals", decision.target_tables)

    def test_cross_domain_fallback_route(self):
        decision = route_question("结合库存和排产，分析哪些产品下周会有缺料风险")
        self.assertEqual(decision.route, "cross_domain")
        self.assertIn("inventory", decision.matched_domains)
        self.assertIn("production", decision.matched_domains)

    def test_legacy_route_for_low_confidence_question(self):
        decision = route_question("你好")
        self.assertEqual(decision.route, "legacy")


if __name__ == "__main__":
    unittest.main()
