import unittest
from decimal import Decimal

from app.execution.sql_executor import _to_jsonable_value


class SqlExecutorTestCase(unittest.TestCase):
    def test_to_jsonable_value_converts_decimal(self):
        self.assertEqual(_to_jsonable_value(Decimal("12")), 12)
        self.assertEqual(_to_jsonable_value(Decimal("12.50")), 12.5)


if __name__ == "__main__":
    unittest.main()
