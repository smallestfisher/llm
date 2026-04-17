from __future__ import annotations

from unittest import mock

from app.config.schema_registry import load_tables_registry
from app import workflow as workflow_pkg
from app.semantic.filters import extract_shared_filters
from app.workflow.router import route_question


def test_rewrite_schema_registry_still_reads_tables_json() -> None:
    tables = load_tables_registry()
    assert "production_actuals" in tables
    assert "daily_inventory" in tables


def test_rewrite_filter_extractor_matches_expected_filters() -> None:
    filters = extract_shared_filters("查看2026W03版本 B4_BJ 工厂下周库存")
    assert filters["PM_VERSION"] == "2026W03"
    assert filters["factory"] == "B4_BJ"
    assert filters["relative_week"] == "next_week"


def test_rewrite_router_carries_filters() -> None:
    with mock.patch.object(workflow_pkg.router, "_llm_route_question", return_value=None):
        decision = route_question("查询最近14天库存风险")
    assert decision.route == "inventory"
    assert decision.filters.get("recent_days") == 14
