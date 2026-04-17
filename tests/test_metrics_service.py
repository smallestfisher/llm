from __future__ import annotations

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from app.services import metrics_service as metrics_module


class MetricsServiceTestCase(unittest.TestCase):
    def test_history_bucket_aggregation(self) -> None:
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(metrics_module, "METRICS_PERSIST_ENABLED", False))
            stack.enter_context(mock.patch.object(metrics_module, "METRICS_MAX_EVENT_AGE_SEC", 86400))
            service = metrics_module.MetricsService()

            with service._lock:
                service._run_events.extend(
                    [
                        (760.0, "completed", "inventory", 1000.0),
                        (780.0, "failed", "inventory", 2000.0),
                        (950.0, "completed", "inventory", 500.0),
                    ]
                )
                service._cache_events.extend(
                    [
                        (770.0, True),
                        (775.0, False),
                        (940.0, True),
                    ]
                )

            with mock.patch("app.services.metrics_service.time.time", return_value=1000.0):
                payload = service.history(window_sec=300, bucket_sec=150, limit=10)

            self.assertEqual(payload["window_sec"], 300)
            self.assertEqual(payload["bucket_sec"], 150)
            self.assertEqual(len(payload["points"]), 2)

            left, right = payload["points"]
            self.assertEqual(left["run_count"], 2)
            self.assertAlmostEqual(left["failure_rate"], 0.5, places=4)
            self.assertAlmostEqual(left["p95_run_ms"], 2000.0, places=2)
            self.assertAlmostEqual(left["cache_hit_rate"], 0.5, places=4)

            self.assertEqual(right["run_count"], 1)
            self.assertAlmostEqual(right["failure_rate"], 0.0, places=4)
            self.assertAlmostEqual(right["p95_run_ms"], 500.0, places=2)
            self.assertAlmostEqual(right["cache_hit_rate"], 1.0, places=4)

    def test_alert_generation_by_thresholds(self) -> None:
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(metrics_module, "METRICS_PERSIST_ENABLED", False))
            stack.enter_context(mock.patch.object(metrics_module, "ALERT_MIN_SAMPLES", 5))
            stack.enter_context(mock.patch.object(metrics_module, "ALERT_FAILURE_RATE_THRESHOLD", 0.3))
            stack.enter_context(mock.patch.object(metrics_module, "ALERT_P95_MS_THRESHOLD", 2000.0))
            stack.enter_context(mock.patch.object(metrics_module, "ALERT_CACHE_HIT_RATE_MIN", 0.2))
            service = metrics_module.MetricsService()

            alerts = service._build_alerts(
                {
                    "run_status": {"completed": 6, "failed": 4},
                    "cache": {"hit": 1, "miss": 9, "hit_rate": 0.1},
                    "nodes": {"__run_total__": {"count": 10, "p95_ms": 3500.0}},
                }
            )

        codes = {item["code"] for item in alerts}
        self.assertEqual(codes, {"high_failure_rate", "high_run_p95", "low_cache_hit_rate"})

    def test_snapshot_includes_run_total_p95(self) -> None:
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(metrics_module, "METRICS_PERSIST_ENABLED", False))
            service = metrics_module.MetricsService()

            with mock.patch("app.services.metrics_service.time.time", side_effect=[10.0, 12.0, 12.0]):
                service.mark_run_started("run-1", route="inventory")
                service.mark_run_finished("run-1", status="completed", route="inventory")
                payload = service.snapshot(window_sec=60)

        run_total = payload["window"]["nodes"].get("__run_total__")
        self.assertIsNotNone(run_total)
        self.assertEqual(run_total["count"], 1)
        self.assertAlmostEqual(run_total["p95_ms"], 2000.0, places=2)

    def test_persistence_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            persist_path = Path(tmp_dir) / "metrics_events.jsonl"

            with ExitStack() as stack:
                stack.enter_context(mock.patch.object(metrics_module, "METRICS_PERSIST_ENABLED", True))
                stack.enter_context(mock.patch.object(metrics_module, "METRICS_PERSIST_PATH", str(persist_path)))
                stack.enter_context(mock.patch.object(metrics_module, "METRICS_MAX_EVENT_AGE_SEC", 86400))
                service = metrics_module.MetricsService()

                with mock.patch(
                    "app.services.metrics_service.time.time",
                    side_effect=[1.0, 1.2, 2.0, 2.1, 2.2],
                ):
                    service.mark_run_started("run-2", route="inventory")
                    service.record_node_event("run-2", node="sql", payload={})
                    service.mark_run_finished("run-2", status="completed", route="inventory")
                    service.record_cache_hit()
                    service.record_cache_miss()

                with mock.patch("app.services.metrics_service.time.time", return_value=3.0):
                    restored = metrics_module.MetricsService()
                    payload = restored.snapshot(window_sec=3600)

            self.assertTrue(persist_path.exists())
            self.assertEqual(payload["run_status"].get("completed"), 1)
            self.assertEqual(payload["cache"]["hit"], 1)
            self.assertEqual(payload["cache"]["miss"], 1)
            self.assertEqual(payload["nodes"].get("sql", {}).get("count"), 1)
            self.assertEqual(payload["window"]["route_counts"].get("inventory"), 1)


if __name__ == "__main__":
    unittest.main()
