import unittest
from decimal import Decimal
from unittest import mock

from app.presentation import answer_builder


class AnswerBuilderTestCase(unittest.TestCase):
    def test_build_answer_payload_handles_decimal_rows(self):
        with mock.patch.object(answer_builder, "llm_complete", return_value="ok"):
            payload = answer_builder.build_answer_payload(
                question="20260416 各厂 TTL 库存还有多少",
                sql_query="SELECT factory_code, SUM(TTL_Qty) AS total_ttl_qty FROM daily_inventory GROUP BY factory_code",
                sql_error="",
                db_result=[["B1", Decimal("12.50")]],
                columns=["factory_code", "total_ttl_qty"],
                row_count=1,
                truncated=False,
                answer_prompt="question={question}\n{db_result}\n{evidence_json}",
            )

        self.assertEqual(payload["row_count"], 1)
        self.assertEqual(payload["table_data"][0]["total_ttl_qty"], 12.5)


if __name__ == "__main__":
    unittest.main()
