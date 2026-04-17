from __future__ import annotations

import json
import os
import time
from threading import Lock
from typing import Any

from app.workflow.state import RouteDecision


QUERY_CACHE_ENABLED = os.getenv("QUERY_CACHE_ENABLED", "1") == "1"
QUERY_CACHE_MAX_SIZE = max(100, int(os.getenv("QUERY_CACHE_MAX_SIZE", "2000")))
QUERY_CACHE_TTL_SHORT = max(30, int(os.getenv("QUERY_CACHE_TTL_SHORT", "180")))
QUERY_CACHE_TTL_LONG = max(60, int(os.getenv("QUERY_CACHE_TTL_LONG", "600")))
QUERY_CACHE_SCHEMA_VERSION = os.getenv("QUERY_CACHE_SCHEMA_VERSION", "v1")
_LONG_TTL_ROUTES = {"planning", "demand", "sales"}


class QueryCacheService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._store: dict[str, dict[str, Any]] = {}

    def enabled(self) -> bool:
        return QUERY_CACHE_ENABLED

    def build_key(self, *, question: str, decision: RouteDecision) -> str:
        normalized_question = (
            str(decision.filters.get("_normalized_question"))
            if isinstance(decision.filters, dict) and decision.filters.get("_normalized_question")
            else (question or "").strip()
        )
        filters = self._stable_filters(decision.filters or {})
        route_scope = decision.route
        if decision.route == "cross_domain":
            route_scope = f"cross_domain:{','.join(decision.matched_domains)}"
        payload = {
            "q": normalized_question,
            "filters": filters,
            "route": route_scope,
            "schema_version": QUERY_CACHE_SCHEMA_VERSION,
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def get(self, key: str) -> dict[str, Any] | None:
        if not self.enabled():
            return None
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            if entry["expires_at"] <= now:
                self._store.pop(key, None)
                return None
            entry["hits"] = int(entry.get("hits", 0)) + 1
            return dict(entry["value"])

    def set(self, *, key: str, value: dict[str, Any], route: str) -> None:
        if not self.enabled():
            return
        ttl = QUERY_CACHE_TTL_LONG if route in _LONG_TTL_ROUTES else QUERY_CACHE_TTL_SHORT
        now = time.time()
        with self._lock:
            self._store[key] = {
                "value": dict(value),
                "created_at": now,
                "expires_at": now + ttl,
                "hits": 0,
            }
            self._prune(now)

    def _prune(self, now: float) -> None:
        expired_keys = [k for k, v in self._store.items() if float(v.get("expires_at", 0.0)) <= now]
        for key in expired_keys:
            self._store.pop(key, None)

        if len(self._store) <= QUERY_CACHE_MAX_SIZE:
            return
        overflow = len(self._store) - QUERY_CACHE_MAX_SIZE
        oldest = sorted(self._store.items(), key=lambda item: float(item[1].get("created_at", 0.0)))[:overflow]
        for key, _ in oldest:
            self._store.pop(key, None)

    @staticmethod
    def _stable_filters(filters: dict[str, Any]) -> dict[str, Any]:
        hidden_keys = {"_normalized_question", "_cross_domain", "_cross_domain_parent_question"}
        stable = {k: v for k, v in filters.items() if k not in hidden_keys}
        try:
            return json.loads(json.dumps(stable, ensure_ascii=False, sort_keys=True))
        except Exception:
            return stable


query_cache_service = QueryCacheService()
