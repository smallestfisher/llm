import json
import sys
import re
import asyncio

from app.workflow.orchestrator import get_compiled_workflow


def is_field_in_sql(sql: str, expected_field: str) -> bool:
    if "." in expected_field:
        table, col = expected_field.split(".", 1)
        pattern_full = rf"\b{table}\.{col}\b"
        pattern_col = rf"\b{col}\b"
        pattern_agg = rf"\b(sum|avg|min|max|count)\s*\(\s*(?:\w+\.)?{col}\s*\)"
        pattern_select_star = rf"\bselect\s+\*\s+from\s+{table}\b"
        alias_match = re.search(rf"\bFROM\s+{table}\s+(\w+)\b", sql, re.IGNORECASE)
        if alias_match:
            alias = alias_match.group(1)
            pattern_alias = rf"\b{alias}\.{col}\b"
            return bool(
                re.search(pattern_full, sql, re.IGNORECASE)
                or re.search(pattern_alias, sql, re.IGNORECASE)
                or re.search(pattern_agg, sql, re.IGNORECASE)
                or re.search(pattern_select_star, sql, re.IGNORECASE)
                or (re.search(rf"\b{table}\b", sql, re.IGNORECASE) and re.search(pattern_col, sql, re.IGNORECASE))
            )
        return bool(
            re.search(pattern_full, sql, re.IGNORECASE)
            or re.search(pattern_agg, sql, re.IGNORECASE)
            or re.search(pattern_select_star, sql, re.IGNORECASE)
            or (re.search(rf"\b{table}\b", sql, re.IGNORECASE) and re.search(pattern_col, sql, re.IGNORECASE))
        )
    return bool(re.search(rf"\b{expected_field}\b", sql, re.IGNORECASE))


async def run_evaluation():
    with open("tests/goldens.json", "r", encoding="utf-8") as f:
        goldens = json.load(f)

    workflow = await get_compiled_workflow()
    passed = 0

    print(f"🚀 开始回归测试，共 {len(goldens)} 条用例...\n")

    for case in goldens:
        question = case["question"]
        expected_field = case.get("expected_field")
        expected_route = case.get("expected_route")
        expected_skill = case.get("expected_skill")
        expected_domains = case.get("expected_domains")

        config = {"configurable": {"thread_id": f"test_{question[:5]}"}}
        result = await workflow.ainvoke({"question": question, "chat_history": []}, config=config)

        sql = result.get("sql_query", "")
        actual_route = result.get("route")
        actual_skill = result.get("active_skill") or result.get("skill_name")
        actual_domains = result.get("route_domains") or []

        checks = []
        if expected_route:
            checks.append(("route", actual_route == expected_route, expected_route, actual_route))
        if expected_skill:
            checks.append(("skill", actual_skill == expected_skill, expected_skill, actual_skill))
        if expected_domains:
            checks.append(
                (
                    "domains",
                    set(actual_domains) == set(expected_domains),
                    expected_domains,
                    actual_domains,
                )
            )
        if expected_field:
            checks.append(("field", is_field_in_sql(sql, expected_field), expected_field, sql))

        failed = [item for item in checks if not item[1]]
        if not failed:
            route_text = actual_route or "-"
            skill_text = actual_skill or "-"
            print(f"✅ PASSED: '{question}' -> route={route_text}, skill={skill_text}")
            passed += 1
        else:
            print(f"❌ FAILED: '{question}'")
            for check_name, _, expected, actual in failed:
                print(f"   校验项: {check_name}")
                print(f"   预期: {expected}")
                print(f"   实际: {actual}")

    print(f"\n测试完成: {passed}/{len(goldens)} 通过。")
    sys.exit(0 if passed == len(goldens) else 1)


if __name__ == "__main__":
    asyncio.run(run_evaluation())
