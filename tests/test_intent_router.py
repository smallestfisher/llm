import unittest
from unittest.mock import patch

from core.router.intent_router import route_question, route_question_by_rules


class IntentRouterTestCase(unittest.TestCase):


    def test_inventory_route(self):
        decision = route_question("查询最近7天库存和在途情况")
        self.assertEqual(decision.route, "inventory")
        self.assertIn("inventory", decision.matched_domains)
        self.assertTrue(decision.target_tables)

    def test_production_route(self):
        decision = route_question("按工厂看最近一周投入和产出情况")
        self.assertEqual(decision.route, "production")
        self.assertIn("production", decision.matched_domains)
        self.assertIn("production_actuals", decision.target_tables)

    def test_production_metric_only_route(self):
        decision = route_question("看下昨天的报废实绩")
        self.assertEqual(decision.route, "production")
        self.assertIn("production_actuals", decision.target_tables)

    def test_production_version_route(self):
        decision = route_question("查看2026W03版本周滚计划")
        self.assertEqual(decision.route, "planning")
        self.assertIn("weekly_rolling_plan", decision.target_tables)

    def test_demand_route(self):
        decision = route_question("查看2026W03版本 forecast 需求缺口")
        self.assertEqual(decision.route, "demand")
        self.assertIn("v_demand", decision.target_tables)

    def test_sales_route(self):
        decision = route_question("查看上个月各客户财务业绩")
        self.assertEqual(decision.route, "sales")
        self.assertIn("sales_financial_perf", decision.target_tables)

    def test_sales_metric_only_route(self):
        decision = route_question("上个月各客户销量")
        self.assertEqual(decision.route, "sales")
        self.assertIn("sales_financial_perf", decision.target_tables)

    def test_cross_domain_fallback_route(self):
        decision = route_question("结合库存和排产，分析哪些产品下周会有缺料风险")
        self.assertEqual(decision.route, "cross_domain")
        self.assertIn("inventory", decision.matched_domains)
        self.assertIn("planning", decision.matched_domains)

    def test_cross_domain_production_vs_plan_route(self):
        decision = route_question("对比本月审批版计划和实际产出差多少")
        self.assertEqual(decision.route, "cross_domain")
        self.assertIn("planning", decision.matched_domains)
        self.assertIn("production", decision.matched_domains)

    def test_legacy_route_for_low_confidence_question(self):
        decision = route_question("你好")
        self.assertEqual(decision.route, "legacy")

    def test_rule_router_keeps_high_confidence_match_without_llm(self):
        decision, _, _, _ = route_question_by_rules("查询最近7天库存和在途情况")
        self.assertEqual(decision.route, "inventory")

    @patch("core.router.intent_router.llm_complete")
    def test_llm_fallback_can_upgrade_legacy_route(self, mock_llm_complete):
        mock_llm_complete.return_value = '{"route": "inventory", "confidence": 0.82, "matched_domains": ["inventory"], "reason": "llm fallback selected inventory"}'
        decision = route_question("帮我看看最近缺货风险")
        self.assertEqual(decision.route, "inventory")
        self.assertIn("inventory", decision.matched_domains)

    @patch("core.router.intent_router.llm_complete")
    def test_llm_fallback_invalid_json_falls_back_to_rules(self, mock_llm_complete):
        mock_llm_complete.return_value = 'not-json'
        decision = route_question("帮我看看最近缺货风险")
        self.assertEqual(decision.route, "legacy")

    @patch("core.router.intent_router.llm_complete")
    def test_llm_fallback_can_select_cross_domain(self, mock_llm_complete):
        mock_llm_complete.return_value = '{"route": "cross_domain", "confidence": 0.88, "matched_domains": ["inventory", "planning"], "reason": "llm fallback selected cross_domain"}'
        decision = route_question("看一下下周会不会缺料以及排产是否支撑")
        self.assertEqual(decision.route, "cross_domain")
        self.assertIn("inventory", decision.matched_domains)
        self.assertIn("planning", decision.matched_domains)


if __name__ == "__main__":
    unittest.main()
