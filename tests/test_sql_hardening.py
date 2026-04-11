import unittest

from core.runtime.skill_runtime import harden_sql, lint_sql


class SqlHardeningTestCase(unittest.TestCase):
    def test_replace_current_month_placeholder(self):
        sql = "SELECT * FROM sales_financial_perf WHERE report_month = CURRENT_MONTH"
        hardened = harden_sql(sql, {"relative_month": "current_month"})
        self.assertIn("DATE_FORMAT(CURDATE(), '%Y-%m')", hardened)
        self.assertNotIn("CURRENT_MONTH", hardened)

    def test_replace_demand_month_alias(self):
        sql = "SELECT SUM(MONTH3) AS future_third_month_commit FROM p_demand"
        hardened = harden_sql(sql, {})
        self.assertIn("LAST_REQUIREMENT", hardened)
        self.assertNotIn("MONTH3", hardened)

    def test_replace_previous_month_placeholder(self):
        sql = "SELECT * FROM sales_financial_perf WHERE report_month = PREVIOUS_MONTH"
        hardened = harden_sql(sql, {"relative_month": "previous_month"})
        self.assertIn("DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m')", hardened)

    def test_expand_select_star_for_known_table(self):
        sql = "SELECT * FROM weekly_rolling_plan WHERE PM_VERSION = '2026W03'"
        hardened = harden_sql(sql, {}, question="把 2026W03 版本周滚计划拉一下", allowed_tables=["weekly_rolling_plan"])
        self.assertIn("PM_VERSION", hardened)
        self.assertIn("plan_qty", hardened)
        self.assertNotIn("SELECT *", hardened.upper())

    def test_strip_inventory_having_without_explicit_threshold(self):
        sql = (
            "SELECT product_ID, SUM(TTL_Qty) AS total_ttl_qty, SUM(HOLD_Qty) AS total_hold_qty "
            "FROM daily_inventory GROUP BY product_ID HAVING total_ttl_qty < 100 OR total_hold_qty < 50"
        )
        hardened = harden_sql(sql, {}, question="结合库存和排产看哪些产品会缺料", domain="inventory")
        self.assertNotIn("HAVING", hardened.upper())

    def test_keep_inventory_having_when_user_specifies_threshold(self):
        sql = (
            "SELECT product_ID, SUM(TTL_Qty) AS total_ttl_qty "
            "FROM daily_inventory GROUP BY product_ID HAVING total_ttl_qty < 100"
        )
        hardened = harden_sql(sql, {}, question="找出 TTL 库存低于100的产品", domain="inventory")
        self.assertIn("HAVING", hardened.upper())

    def test_lint_requires_version_filter(self):
        sql = "SELECT PM_VERSION, plan_qty FROM weekly_rolling_plan"
        issues = lint_sql(
            sql,
            question="查看2026W03版本周滚计划",
            domain="planning",
            structured_filters={"PM_VERSION": "2026W03"},
            allowed_tables=["weekly_rolling_plan"],
        )
        self.assertTrue(any("版本过滤条件" in issue for issue in issues))

    def test_lint_blocks_meaningless_sales_helper_join(self):
        sql = (
            "SELECT s.report_month, s.sales_qty FROM sales_financial_perf s "
            "JOIN product_attributes pa ON s.FGCODE = pa.product_ID"
        )
        issues = lint_sql(
            sql,
            question="按 BU 看这个月销售量",
            domain="sales",
            structured_filters={"relative_month": "current_month"},
            allowed_tables=["sales_financial_perf", "product_attributes", "product_mapping"],
        )
        self.assertTrue(any("无意义 JOIN" in issue for issue in issues))

    def test_lint_blocks_select_star(self):
        sql = "SELECT * FROM weekly_rolling_plan WHERE PM_VERSION = '2026W03'"
        issues = lint_sql(
            sql,
            question="把 2026W03 版本周滚计划拉一下",
            domain="planning",
            structured_filters={"PM_VERSION": "2026W03"},
            allowed_tables=["weekly_rolling_plan"],
        )
        self.assertTrue(any("SELECT *" in issue for issue in issues))

    def test_lint_blocks_placeholder_literals(self):
        sql = (
            "SELECT SUM(plan_qty) FROM weekly_rolling_plan "
            "WHERE factory = 'your_factory_code' AND product_ID = 'your_product_ID'"
        )
        issues = lint_sql(
            sql,
            question="库存能否支撑下周排产",
            domain="planning",
            structured_filters={"relative_week": "next_week"},
            allowed_tables=["weekly_rolling_plan"],
        )
        self.assertTrue(any("占位或示例字面值" in issue for issue in issues))

    def test_strip_suspicious_literal_filters(self):
        sql = (
            "SELECT SUM(plan_qty) FROM weekly_rolling_plan "
            "WHERE plan_date >= CURDATE() AND factory = 'FACTORY001' AND product_ID = 'PRODUCT123'"
        )
        hardened = harden_sql(sql, {}, question="库存能否支撑下周排产", domain="planning")
        self.assertNotIn("FACTORY001", hardened)
        self.assertNotIn("PRODUCT123", hardened)
        self.assertIn("plan_date >=", hardened)

    def test_quote_spaced_columns(self):
        sql = "SELECT FGCODE FROM product_mapping WHERE Cell No = 'B4_BJ'"
        hardened = harden_sql(sql, {}, question="今天 B4_BJ 的日排产是多少", domain="planning")
        self.assertIn("`Cell No`", hardened)


if __name__ == "__main__":
    unittest.main()
