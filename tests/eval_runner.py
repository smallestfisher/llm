from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

from app.workflow.orchestrator import get_compiled_workflow


ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "tests" / "evals"
DEFAULT_GOLDENS = ROOT / "tests" / "goldens.json"
THRESHOLDS_PATH = EVAL_DIR / "thresholds.json"
ANSWER_CASES_PATH = EVAL_DIR / "answer_cases.json"
REPORT_PATH = EVAL_DIR / "report_latest.json"


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


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _safe_ratio(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _evaluate_answer_rules(cases: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    total = 0
    passed = 0
    details: list[dict[str, Any]] = []

    for case in cases:
        answer = str(case.get("answer", ""))
        must_contain = [str(item) for item in (case.get("must_contain") or [])]
        must_not_contain = [str(item) for item in (case.get("must_not_contain") or [])]
        case_id = str(case.get("id") or f"answer_case_{total + 1}")
        failures: list[str] = []

        for token in must_contain:
            if token not in answer:
                failures.append(f"missing:{token}")
        for token in must_not_contain:
            if token and token in answer:
                failures.append(f"forbidden:{token}")

        total += 1
        ok = len(failures) == 0
        if ok:
            passed += 1
        details.append({"id": case_id, "passed": ok, "failures": failures, "answer": answer})

    summary = {
        "case_total": total,
        "case_passed": passed,
        "case_pass_rate": round(_safe_ratio(passed, total), 4),
    }
    return summary, details


async def run_evaluation(
    goldens_path: Path,
    strict: bool = True,
    max_cases: int = 0,
    case_timeout_sec: float = 45.0,
) -> int:
    goldens = _load_json(goldens_path, [])
    if max_cases > 0:
        goldens = goldens[:max_cases]
    thresholds_payload = _load_json(
        THRESHOLDS_PATH,
        {
            "min_cases": 10,
            "thresholds": {
                "route_top1_accuracy": 0.8,
                "sql_field_hit_rate": 0.75,
                "first_sql_success_rate": 0.7,
                "no_data_guard_rate": 0.95,
                "answer_rule_case_pass_rate": 1.0,
            },
        },
    )
    answer_cases = _load_json(ANSWER_CASES_PATH, [])

    workflow = await get_compiled_workflow()

    counters = {
        "route_total": 0,
        "route_passed": 0,
        "skill_total": 0,
        "skill_passed": 0,
        "domain_total": 0,
        "domain_passed": 0,
        "field_total": 0,
        "field_passed": 0,
        "sql_exec_total": 0,
        "sql_exec_passed": 0,
        "no_data_total": 0,
        "no_data_passed": 0,
    }
    case_details: list[dict[str, Any]] = []

    print(f"开始评测，共 {len(goldens)} 条 workflow 用例")

    for index, case in enumerate(goldens, start=1):
        question = str(case.get("question", "")).strip()
        if not question:
            continue
        expected_route = case.get("expected_route")
        expected_skill = case.get("expected_skill")
        expected_domains = case.get("expected_domains")
        expected_field = case.get("expected_field")

        result: dict[str, Any] = {}
        runtime_error = ""
        try:
            result = await asyncio.wait_for(
                workflow.ainvoke({"question": question, "chat_history": []}, config={}),
                timeout=max(5.0, float(case_timeout_sec)),
            )
        except Exception as exc:
            runtime_error = str(exc)

        sql = str(result.get("sql_query") or "")
        sql_error = str(result.get("sql_error") or "")
        final_answer = str(result.get("final_answer") or "")
        db_result = result.get("db_result") or []
        actual_route = result.get("route")
        actual_skill = result.get("active_skill") or result.get("skill_name")
        actual_domains = result.get("route_domains") or []

        checks: dict[str, bool] = {}
        if expected_route:
            counters["route_total"] += 1
            checks["route"] = actual_route == expected_route
            if checks["route"]:
                counters["route_passed"] += 1

        if expected_skill:
            counters["skill_total"] += 1
            checks["skill"] = actual_skill == expected_skill
            if checks["skill"]:
                counters["skill_passed"] += 1

        if expected_domains:
            counters["domain_total"] += 1
            checks["domains"] = set(actual_domains) == set(expected_domains)
            if checks["domains"]:
                counters["domain_passed"] += 1

        if expected_field:
            counters["field_total"] += 1
            checks["field"] = is_field_in_sql(sql, str(expected_field))
            if checks["field"]:
                counters["field_passed"] += 1

        counters["sql_exec_total"] += 1
        sql_ok = bool(sql and not sql_error and not runtime_error)
        if sql_ok:
            counters["sql_exec_passed"] += 1

        if not db_result:
            counters["no_data_total"] += 1
            no_data_ok = "未查到" in final_answer
            if no_data_ok:
                counters["no_data_passed"] += 1
            checks["no_data_guard"] = no_data_ok

        case_passed = runtime_error == "" and all(checks.values()) if checks else runtime_error == ""
        case_details.append(
            {
                "index": index,
                "question": question,
                "passed": case_passed,
                "runtime_error": runtime_error,
                "checks": checks,
                "actual": {
                    "route": actual_route,
                    "skill": actual_skill,
                    "domains": actual_domains,
                    "sql_error": sql_error,
                    "sql_query": sql,
                },
            }
        )

        status = "PASS" if case_passed else "FAIL"
        print(f"[{index:02d}] {status} - {question}")

    answer_summary, answer_details = _evaluate_answer_rules(answer_cases if isinstance(answer_cases, list) else [])

    metrics = {
        "route_top1_accuracy": round(_safe_ratio(counters["route_passed"], counters["route_total"]), 4),
        "skill_accuracy": round(_safe_ratio(counters["skill_passed"], counters["skill_total"]), 4),
        "domain_set_accuracy": round(_safe_ratio(counters["domain_passed"], counters["domain_total"]), 4),
        "sql_field_hit_rate": round(_safe_ratio(counters["field_passed"], counters["field_total"]), 4),
        "first_sql_success_rate": round(_safe_ratio(counters["sql_exec_passed"], counters["sql_exec_total"]), 4),
        "no_data_guard_rate": round(_safe_ratio(counters["no_data_passed"], counters["no_data_total"]), 4),
        "answer_rule_case_pass_rate": answer_summary["case_pass_rate"],
    }

    thresholds = dict((thresholds_payload or {}).get("thresholds") or {})
    min_cases = int((thresholds_payload or {}).get("min_cases") or 0)
    total_workflow_cases = len(case_details)

    gating: list[dict[str, Any]] = []
    gating_failed = False
    if total_workflow_cases < min_cases:
        gating_failed = True
        gating.append(
            {
                "metric": "case_total",
                "actual": total_workflow_cases,
                "threshold": min_cases,
                "passed": False,
                "reason": "insufficient_case_count",
            }
        )

    for key, threshold in thresholds.items():
        actual = float(metrics.get(key, 0.0))
        passed = actual >= float(threshold)
        if not passed:
            gating_failed = True
        gating.append(
            {
                "metric": key,
                "actual": round(actual, 4),
                "threshold": float(threshold),
                "passed": passed,
            }
        )

    report = {
        "summary": {
            "strict_mode": strict,
            "workflow_case_total": total_workflow_cases,
            "workflow_case_passed": sum(1 for item in case_details if item["passed"]),
            "workflow_case_pass_rate": round(
                _safe_ratio(sum(1 for item in case_details if item["passed"]), total_workflow_cases),
                4,
            ),
            "answer_case_total": answer_summary["case_total"],
            "answer_case_passed": answer_summary["case_passed"],
            "answer_case_pass_rate": answer_summary["case_pass_rate"],
        },
        "metrics": metrics,
        "gating": gating,
        "gating_failed": gating_failed,
        "details": {
            "workflow_cases": case_details,
            "answer_cases": answer_details,
        },
    }

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n关键指标:")
    for key, value in metrics.items():
        print(f"- {key}: {value}")
    print(f"\n报告输出: {REPORT_PATH}")

    if strict and gating_failed:
        print("\n门禁未通过")
        return 1
    print("\n门禁通过")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline route/sql/answer evals with gating.")
    parser.add_argument("--goldens", default=str(DEFAULT_GOLDENS), help="Path to workflow eval cases json")
    parser.add_argument("--no-strict", action="store_true", help="Do not fail process on gating failures")
    parser.add_argument("--max-cases", type=int, default=0, help="Only run first N workflow cases (0 = all)")
    parser.add_argument("--case-timeout-sec", type=float, default=45.0, help="Per-case timeout in seconds")
    return parser.parse_args()


async def _main() -> int:
    args = parse_args()
    return await run_evaluation(
        Path(args.goldens),
        strict=not args.no_strict,
        max_cases=max(0, int(args.max_cases)),
        case_timeout_sec=max(5.0, float(args.case_timeout_sec)),
    )


if __name__ == "__main__":
    exit_code = asyncio.run(_main())
    sys.exit(exit_code)
