from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate markdown acceptance report from eval + metrics artifacts.")
    parser.add_argument("--eval", default="tests/evals/report_latest.json", help="eval report json path")
    parser.add_argument("--metrics", default="tests/evals/metrics_snapshot.json", help="metrics snapshot json path")
    parser.add_argument("--output", default="tests/evals/acceptance_latest.md", help="markdown output path")
    return parser.parse_args()


def _to_percent(value: float | int | None) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value) * 100:.2f}%"
    except Exception:
        return "-"


def _render_gating(gating: list[dict[str, Any]]) -> str:
    if not gating:
        return "| Metric | Actual | Threshold | Passed |\n|---|---:|---:|:---:|\n| - | - | - | - |\n"
    lines = ["| Metric | Actual | Threshold | Passed |", "|---|---:|---:|:---:|"]
    for item in gating:
        lines.append(
            f"| {item.get('metric', '-')} | {item.get('actual', '-')} | {item.get('threshold', '-')} | {'Y' if item.get('passed') else 'N'} |"
        )
    return "\n".join(lines) + "\n"


def _render_alerts(alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return "- 无告警\n"
    lines = []
    for alert in alerts:
        lines.append(
            f"- [{alert.get('level', 'info')}] `{alert.get('code', '-')}` {alert.get('message', '')} "
            f"(value={alert.get('value', '-')}, threshold={alert.get('threshold', '-')})"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    eval_payload = _load_json(Path(args.eval))
    metrics_payload = _load_json(Path(args.metrics))

    summary = dict(eval_payload.get("summary") or {})
    metrics = dict(eval_payload.get("metrics") or {})
    gating = list(eval_payload.get("gating") or [])
    gating_failed = bool(eval_payload.get("gating_failed"))

    metrics_snapshot = dict(metrics_payload.get("snapshot") or {})
    history = dict(metrics_payload.get("history") or {})
    alerts = list(metrics_snapshot.get("alerts") or [])

    report_lines = [
        "# Acceptance Report",
        "",
        f"- Gate Status: {'FAILED' if gating_failed else 'PASSED'}",
        f"- Workflow Cases: {summary.get('workflow_case_passed', 0)}/{summary.get('workflow_case_total', 0)}",
        f"- Answer Rule Cases: {summary.get('answer_case_passed', 0)}/{summary.get('answer_case_total', 0)}",
        "",
        "## Eval Metrics",
        "",
        f"- route_top1_accuracy: {_to_percent(metrics.get('route_top1_accuracy'))}",
        f"- sql_field_hit_rate: {_to_percent(metrics.get('sql_field_hit_rate'))}",
        f"- first_sql_success_rate: {_to_percent(metrics.get('first_sql_success_rate'))}",
        f"- no_data_guard_rate: {_to_percent(metrics.get('no_data_guard_rate'))}",
        f"- answer_rule_case_pass_rate: {_to_percent(metrics.get('answer_rule_case_pass_rate'))}",
        "",
        "## Gating",
        "",
        _render_gating(gating),
        "## Runtime Metrics",
        "",
        f"- Uptime: {metrics_snapshot.get('uptime_sec', 0)}s",
        f"- Inflight Runs: {metrics_snapshot.get('inflight_runs', 0)}",
        f"- Cache Hit Rate: {_to_percent((metrics_snapshot.get('cache') or {}).get('hit_rate'))}",
        f"- History Points: {len(history.get('points') or [])}",
        "",
        "## Alerts",
        "",
        _render_alerts(alerts),
    ]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"acceptance report saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
