from __future__ import annotations

import json
import os
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from app.logging_config import get_logger


logger = get_logger(__name__)


def _empty_latency_bucket() -> dict[str, float]:
    return {"count": 0.0, "sum_ms": 0.0, "max_ms": 0.0}


METRICS_DEFAULT_WINDOW_SEC = max(60, int(os.getenv("METRICS_DEFAULT_WINDOW_SEC", "900")))
METRICS_MAX_EVENT_AGE_SEC = max(METRICS_DEFAULT_WINDOW_SEC, int(os.getenv("METRICS_MAX_EVENT_AGE_SEC", "86400")))
METRICS_MAX_NODE_SAMPLES = max(200, int(os.getenv("METRICS_MAX_NODE_SAMPLES", "5000")))
METRICS_MAX_CACHE_EVENTS = max(200, int(os.getenv("METRICS_MAX_CACHE_EVENTS", "5000")))
METRICS_MAX_RUN_EVENTS = max(200, int(os.getenv("METRICS_MAX_RUN_EVENTS", "5000")))

METRICS_PERSIST_ENABLED = os.getenv("METRICS_PERSIST_ENABLED", "1") == "1"
METRICS_PERSIST_PATH = os.getenv("METRICS_PERSIST_PATH", "backend/data/metrics_events.jsonl")

ALERT_FAILURE_RATE_THRESHOLD = float(os.getenv("ALERT_FAILURE_RATE_THRESHOLD", "0.2"))
ALERT_P95_MS_THRESHOLD = float(os.getenv("ALERT_P95_MS_THRESHOLD", "15000"))
ALERT_CACHE_HIT_RATE_MIN = float(os.getenv("ALERT_CACHE_HIT_RATE_MIN", "0.2"))
ALERT_MIN_SAMPLES = max(5, int(os.getenv("ALERT_MIN_SAMPLES", "20")))
ALERT_COOLDOWN_SEC = max(30, int(os.getenv("ALERT_COOLDOWN_SEC", "300")))


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95 + 0.5) - 1))
    return float(ordered[index])


class MetricsService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at = time.time()
        self._run_tracker: dict[str, dict[str, Any]] = {}
        self._route_counts: dict[str, int] = defaultdict(int)
        self._run_status_counts: dict[str, int] = defaultdict(int)
        self._node_latency: dict[str, dict[str, float]] = defaultdict(_empty_latency_bucket)
        self._node_failures: dict[str, int] = defaultdict(int)
        self._cache_counts: dict[str, int] = defaultdict(int)
        self._node_samples: dict[str, deque[tuple[float, float, bool]]] = defaultdict(
            lambda: deque(maxlen=METRICS_MAX_NODE_SAMPLES)
        )
        self._cache_events: deque[tuple[float, bool]] = deque(maxlen=METRICS_MAX_CACHE_EVENTS)
        self._run_events: deque[tuple[float, str, str, float]] = deque(maxlen=METRICS_MAX_RUN_EVENTS)
        self._persist_path = Path(METRICS_PERSIST_PATH)
        self._last_alert_ts: dict[str, float] = {}
        self._load_persisted_events()

    def mark_run_started(self, run_id: str, *, route: str = "") -> None:
        now = time.time()
        with self._lock:
            self._run_tracker[run_id] = {"started_at": now, "last_ts": now, "route": route}
            if route:
                self._route_counts[route] += 1
            self._prune_old(now)

    def mark_run_route(self, run_id: str, route: str) -> None:
        if not route:
            return
        with self._lock:
            tracker = self._run_tracker.get(run_id)
            if not tracker:
                return
            previous_route = tracker.get("route") or ""
            if previous_route != route:
                self._route_counts[route] += 1
                tracker["route"] = route

    def record_node_event(self, run_id: str, *, node: str, payload: dict[str, Any] | None = None) -> None:
        payload = payload or {}
        now = time.time()
        with self._lock:
            tracker = self._run_tracker.get(run_id)
            if not tracker:
                tracker = {"started_at": now, "last_ts": now, "route": ""}
                self._run_tracker[run_id] = tracker
            elapsed_ms = max(0.0, (now - float(tracker.get("last_ts", now))) * 1000.0)
            tracker["last_ts"] = now

            bucket = self._node_latency[node]
            bucket["count"] += 1
            bucket["sum_ms"] += elapsed_ms
            bucket["max_ms"] = max(bucket["max_ms"], elapsed_ms)

            failed = bool(payload.get("sql_error"))
            if failed:
                self._node_failures[node] += 1
            self._node_samples[node].append((now, elapsed_ms, failed))
            self._persist_event(
                {
                    "type": "node",
                    "ts": now,
                    "node": node,
                    "latency_ms": round(elapsed_ms, 3),
                    "failed": failed,
                }
            )
            self._prune_old(now)

    def record_cache_hit(self) -> None:
        with self._lock:
            self._cache_counts["hit"] += 1
            now = time.time()
            self._cache_events.append((now, True))
            self._persist_event({"type": "cache", "ts": now, "hit": True})
            self._prune_old(now)

    def record_cache_miss(self) -> None:
        with self._lock:
            self._cache_counts["miss"] += 1
            now = time.time()
            self._cache_events.append((now, False))
            self._persist_event({"type": "cache", "ts": now, "hit": False})
            self._prune_old(now)

    def mark_run_finished(self, run_id: str, *, status: str, route: str = "") -> None:
        now = time.time()
        with self._lock:
            tracker = self._run_tracker.pop(run_id, None)
            self._run_status_counts[status] += 1
            if route and tracker and not tracker.get("route"):
                self._route_counts[route] += 1
            if tracker:
                total_ms = max(0.0, (now - float(tracker.get("started_at", now))) * 1000.0)
                bucket = self._node_latency["__run_total__"]
                bucket["count"] += 1
                bucket["sum_ms"] += total_ms
                bucket["max_ms"] = max(bucket["max_ms"], total_ms)
                self._node_samples["__run_total__"].append((now, total_ms, status == "failed"))
                final_route = route or str(tracker.get("route") or "")
                self._run_events.append((now, status, final_route, total_ms))
                self._persist_event(
                    {
                        "type": "run",
                        "ts": now,
                        "status": status,
                        "route": final_route,
                        "total_ms": round(total_ms, 3),
                    }
                )
            self._prune_old(now)

    def history(self, *, window_sec: int = 86400, bucket_sec: int = 300, limit: int = 96) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            self._prune_old(now)
            bucket_sec = max(60, int(bucket_sec))
            limit = max(1, min(500, int(limit)))
            effective_window = max(bucket_sec, min(int(window_sec), bucket_sec * limit))
            start_ts = now - effective_window
            points: list[dict[str, Any]] = []
            bucket_count = max(1, int(effective_window / bucket_sec))
            for index in range(bucket_count):
                bucket_start = start_ts + (index * bucket_sec)
                points.append(
                    {
                        "ts": int(bucket_start),
                        "run_total": 0,
                        "run_failed": 0,
                        "run_latencies": [],
                        "cache_hit": 0,
                        "cache_miss": 0,
                    }
                )

            for ts, status, _, total_ms in self._run_events:
                if ts < start_ts:
                    continue
                bucket_idx = int((ts - start_ts) // bucket_sec)
                if bucket_idx < 0 or bucket_idx >= len(points):
                    continue
                point = points[bucket_idx]
                point["run_total"] += 1
                if status == "failed":
                    point["run_failed"] += 1
                point["run_latencies"].append(float(total_ms))

            for ts, is_hit in self._cache_events:
                if ts < start_ts:
                    continue
                bucket_idx = int((ts - start_ts) // bucket_sec)
                if bucket_idx < 0 or bucket_idx >= len(points):
                    continue
                point = points[bucket_idx]
                if is_hit:
                    point["cache_hit"] += 1
                else:
                    point["cache_miss"] += 1

            result_points: list[dict[str, Any]] = []
            for point in points:
                run_total = int(point["run_total"])
                run_failed = int(point["run_failed"])
                cache_total = int(point["cache_hit"]) + int(point["cache_miss"])
                latencies = [float(v) for v in point["run_latencies"]]
                result_points.append(
                    {
                        "ts": point["ts"],
                        "run_count": run_total,
                        "failure_rate": round((run_failed / run_total) if run_total else 0.0, 4),
                        "p95_run_ms": round(_p95(latencies), 2),
                        "cache_hit_rate": round((int(point["cache_hit"]) / cache_total) if cache_total else 0.0, 4),
                    }
                )

            return {
                "window_sec": effective_window,
                "bucket_sec": bucket_sec,
                "points": result_points,
            }

    def snapshot(self, *, window_sec: int | None = None) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            self._prune_old(now)
            nodes = {}
            for node, bucket in self._node_latency.items():
                count = int(bucket["count"])
                avg_ms = (bucket["sum_ms"] / count) if count else 0.0
                sample_latencies = [latency for _, latency, _ in self._node_samples.get(node, [])]
                failures = int(self._node_failures.get(node, 0))
                nodes[node] = {
                    "count": count,
                    "avg_ms": round(avg_ms, 2),
                    "max_ms": round(bucket["max_ms"], 2),
                    "p95_ms": round(_p95(sample_latencies), 2),
                    "failure_count": failures,
                    "failure_rate": round((failures / count) if count else 0.0, 4),
                }

            hit = int(self._cache_counts.get("hit", 0))
            miss = int(self._cache_counts.get("miss", 0))
            total = hit + miss
            cache_hit_rate = (hit / total) if total else 0.0
            effective_window = max(60, int(window_sec or METRICS_DEFAULT_WINDOW_SEC))
            window_snapshot = self._window_snapshot(now, effective_window)
            alerts = self._build_alerts(window_snapshot)
            self._emit_alert_logs(alerts, now)

            return {
                "uptime_sec": int(now - self._started_at),
                "inflight_runs": len(self._run_tracker),
                "run_status": dict(self._run_status_counts),
                "route_counts": dict(self._route_counts),
                "cache": {
                    "hit": hit,
                    "miss": miss,
                    "hit_rate": round(cache_hit_rate, 4),
                },
                "nodes": nodes,
                "window": window_snapshot,
                "window_sec": effective_window,
                "alerts": alerts,
            }

    def _window_snapshot(self, now: float, window_sec: int) -> dict[str, Any]:
        cutoff = now - window_sec
        window_cache_hit = 0
        window_cache_miss = 0
        for ts, is_hit in self._cache_events:
            if ts < cutoff:
                continue
            if is_hit:
                window_cache_hit += 1
            else:
                window_cache_miss += 1
        window_cache_total = window_cache_hit + window_cache_miss

        window_run_status: dict[str, int] = defaultdict(int)
        window_route_counts: dict[str, int] = defaultdict(int)
        for ts, status, route, _ in self._run_events:
            if ts < cutoff:
                continue
            window_run_status[status] += 1
            if route:
                window_route_counts[route] += 1

        window_nodes: dict[str, Any] = {}
        for node, samples in self._node_samples.items():
            rows = [(latency, failed) for ts, latency, failed in samples if ts >= cutoff]
            if not rows:
                continue
            latencies = [latency for latency, _ in rows]
            failures = sum(1 for _, failed in rows if failed)
            count = len(rows)
            window_nodes[node] = {
                "count": count,
                "avg_ms": round(sum(latencies) / count, 2),
                "p95_ms": round(_p95(latencies), 2),
                "max_ms": round(max(latencies), 2),
                "failure_count": failures,
                "failure_rate": round((failures / count) if count else 0.0, 4),
            }

        return {
            "window_sec": window_sec,
            "run_status": dict(window_run_status),
            "route_counts": dict(window_route_counts),
            "cache": {
                "hit": window_cache_hit,
                "miss": window_cache_miss,
                "hit_rate": round((window_cache_hit / window_cache_total) if window_cache_total else 0.0, 4),
            },
            "nodes": window_nodes,
        }

    def _build_alerts(self, window_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        run_status = window_snapshot.get("run_status") or {}
        finished_total = int(run_status.get("completed", 0)) + int(run_status.get("failed", 0))
        failed = int(run_status.get("failed", 0))
        failure_rate = (failed / finished_total) if finished_total else 0.0
        if finished_total >= ALERT_MIN_SAMPLES and failure_rate >= ALERT_FAILURE_RATE_THRESHOLD:
            alerts.append(
                {
                    "level": "warning",
                    "code": "high_failure_rate",
                    "value": round(failure_rate, 4),
                    "threshold": ALERT_FAILURE_RATE_THRESHOLD,
                    "message": f"窗口失败率偏高: {failure_rate:.2%}",
                }
            )

        run_total = (window_snapshot.get("nodes") or {}).get("__run_total__") or {}
        run_total_count = int(run_total.get("count") or 0)
        run_total_p95 = float(run_total.get("p95_ms") or 0.0)
        if run_total_count >= ALERT_MIN_SAMPLES and run_total_p95 >= ALERT_P95_MS_THRESHOLD:
            alerts.append(
                {
                    "level": "warning",
                    "code": "high_run_p95",
                    "value": round(run_total_p95, 2),
                    "threshold": ALERT_P95_MS_THRESHOLD,
                    "message": f"端到端 P95 偏高: {run_total_p95:.0f}ms",
                }
            )

        cache = window_snapshot.get("cache") or {}
        cache_total = int(cache.get("hit", 0)) + int(cache.get("miss", 0))
        cache_hit_rate = float(cache.get("hit_rate") or 0.0)
        if cache_total >= ALERT_MIN_SAMPLES and cache_hit_rate < ALERT_CACHE_HIT_RATE_MIN:
            alerts.append(
                {
                    "level": "info",
                    "code": "low_cache_hit_rate",
                    "value": round(cache_hit_rate, 4),
                    "threshold": ALERT_CACHE_HIT_RATE_MIN,
                    "message": f"缓存命中率偏低: {cache_hit_rate:.2%}",
                }
            )
        return alerts

    def _emit_alert_logs(self, alerts: list[dict[str, Any]], now: float) -> None:
        for alert in alerts:
            code = str(alert.get("code") or "")
            if not code:
                continue
            last_ts = float(self._last_alert_ts.get(code, 0.0))
            if now - last_ts < ALERT_COOLDOWN_SEC:
                continue
            self._last_alert_ts[code] = now
            logger.warning(
                "metrics_alert code={} level={} value={} threshold={} message={}",
                code,
                alert.get("level"),
                alert.get("value"),
                alert.get("threshold"),
                alert.get("message"),
            )

    def _prune_old(self, now: float) -> None:
        cutoff = now - METRICS_MAX_EVENT_AGE_SEC
        while self._cache_events and self._cache_events[0][0] < cutoff:
            self._cache_events.popleft()
        while self._run_events and self._run_events[0][0] < cutoff:
            self._run_events.popleft()
        for node, samples in list(self._node_samples.items()):
            while samples and samples[0][0] < cutoff:
                samples.popleft()
            if not samples:
                self._node_samples[node] = deque(maxlen=METRICS_MAX_NODE_SAMPLES)

    def _load_persisted_events(self) -> None:
        if not METRICS_PERSIST_ENABLED:
            return
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            if not self._persist_path.exists():
                return
            cutoff = time.time() - METRICS_MAX_EVENT_AGE_SEC
            with self._persist_path.open("r", encoding="utf-8") as fp:
                for raw_line in fp:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except Exception:
                        continue
                    ts = float(payload.get("ts", 0.0))
                    if ts < cutoff:
                        continue
                    event_type = str(payload.get("type") or "")
                    if event_type == "cache":
                        hit = bool(payload.get("hit"))
                        self._cache_events.append((ts, hit))
                        self._cache_counts["hit" if hit else "miss"] += 1
                    elif event_type == "run":
                        status = str(payload.get("status") or "")
                        route = str(payload.get("route") or "")
                        total_ms = float(payload.get("total_ms") or 0.0)
                        self._run_events.append((ts, status, route, total_ms))
                        if status:
                            self._run_status_counts[status] += 1
                        if route:
                            self._route_counts[route] += 1
                        if total_ms > 0:
                            bucket = self._node_latency["__run_total__"]
                            bucket["count"] += 1
                            bucket["sum_ms"] += total_ms
                            bucket["max_ms"] = max(bucket["max_ms"], total_ms)
                            self._node_samples["__run_total__"].append((ts, total_ms, status == "failed"))
                    elif event_type == "node":
                        node = str(payload.get("node") or "")
                        if not node:
                            continue
                        latency_ms = float(payload.get("latency_ms") or 0.0)
                        failed = bool(payload.get("failed"))
                        self._node_samples[node].append((ts, latency_ms, failed))
                        bucket = self._node_latency[node]
                        bucket["count"] += 1
                        bucket["sum_ms"] += latency_ms
                        bucket["max_ms"] = max(bucket["max_ms"], latency_ms)
                        if failed:
                            self._node_failures[node] += 1
            logger.info("metrics persistence loaded path={}", str(self._persist_path))
        except Exception as exc:
            logger.warning("metrics persistence load failed path={} err={}", str(self._persist_path), str(exc))

    def _persist_event(self, payload: dict[str, Any]) -> None:
        if not METRICS_PERSIST_ENABLED:
            return
        try:
            with self._persist_path.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("metrics persistence write failed path={} err={}", str(self._persist_path), str(exc))


metrics_service = MetricsService()
