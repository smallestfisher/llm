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
    parser = argparse.ArgumentParser(description="Suggest env tuning values from eval + metrics artifacts.")
    parser.add_argument("--eval", default="tests/evals/report_latest.json")
    parser.add_argument("--metrics", default="tests/evals/metrics_snapshot.json")
    parser.add_argument("--output", default="tests/evals/tuning_recommendations.env")
    return parser.parse_args()


def _bool_to_str(value: bool) -> str:
    return "1" if value else "0"


def main() -> int:
    args = parse_args()
    eval_payload = _load_json(Path(args.eval))
    metrics_payload = _load_json(Path(args.metrics))

    eval_metrics = dict(eval_payload.get("metrics") or {})
    snapshot = dict((metrics_payload.get("snapshot") or {}))
    window = dict(snapshot.get("window") or {})
    window_nodes = dict(window.get("nodes") or {})
    run_total = dict(window_nodes.get("__run_total__") or {})
    cache = dict(window.get("cache") or {})

    sql_success = float(eval_metrics.get("first_sql_success_rate") or 0.0)
    route_acc = float(eval_metrics.get("route_top1_accuracy") or 0.0)
    cache_hit_rate = float(cache.get("hit_rate") or 0.0)
    run_p95_ms = float(run_total.get("p95_ms") or 0.0)

    recommend_candidate_count = 2
    recommend_expand_score = 90
    recommend_parallel = 2
    recommend_timeout = 120

    if sql_success < 0.75:
        recommend_candidate_count = 3
        recommend_expand_score = 95
    elif sql_success >= 0.9:
        recommend_candidate_count = 1
        recommend_expand_score = 80

    if run_p95_ms > 20000:
        recommend_parallel = 1
        recommend_timeout = 180
    elif run_p95_ms < 8000 and route_acc >= 0.9:
        recommend_parallel = 2
        recommend_timeout = 120

    recommend_cache_enabled = cache_hit_rate < 0.95
    recommend_cache_short_ttl = 300 if cache_hit_rate < 0.2 else 180
    recommend_cache_long_ttl = 1200 if cache_hit_rate < 0.2 else 600

    lines = [
        "# Auto-generated tuning recommendations",
        f"SQL_CANDIDATE_COUNT={recommend_candidate_count}",
        f"SQL_CANDIDATE_EXPAND_SCORE={recommend_expand_score}",
        f"CROSS_DOMAIN_MAX_PARALLEL={recommend_parallel}",
        f"LLM_TIMEOUT_SECONDS={recommend_timeout}",
        f"QUERY_CACHE_ENABLED={_bool_to_str(recommend_cache_enabled)}",
        f"QUERY_CACHE_TTL_SHORT={recommend_cache_short_ttl}",
        f"QUERY_CACHE_TTL_LONG={recommend_cache_long_ttl}",
    ]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"tuning recommendations saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
