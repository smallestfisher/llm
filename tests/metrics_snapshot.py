from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.metrics_service import metrics_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export metrics snapshot and history to json file.")
    parser.add_argument("--window-sec", type=int, default=900, help="window_sec for snapshot")
    parser.add_argument("--history-window-sec", type=int, default=86400, help="window_sec for history")
    parser.add_argument("--bucket-sec", type=int, default=300, help="bucket_sec for history")
    parser.add_argument("--limit", type=int, default=96, help="max history points")
    parser.add_argument("--output", default="tests/evals/metrics_snapshot.json", help="output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = metrics_service.snapshot(window_sec=args.window_sec)
    history = metrics_service.history(
        window_sec=args.history_window_sec,
        bucket_sec=args.bucket_sec,
        limit=args.limit,
    )
    payload = {
        "snapshot": snapshot,
        "history": history,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"metrics snapshot saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
