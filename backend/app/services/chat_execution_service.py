from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.logging_config import get_logger
from app.models import Run, Thread, Turn, utcnow
from app.services.cache_service import query_cache_service
from app.services.chat_service import ChatService
from app.services.conversation_resolver import ConversationResolver
from app.services.metrics_service import metrics_service
from app.services.thread_event_publisher import thread_event_publisher
from app.services.run_service import ACTIVE_RUN_STATUSES, RunService
from app.workflow.executor import execute_chat_workflow
from app.workflow.router import route_question_for_state
from app.workflow.state import CancelledError, RouteDecision

logger = get_logger(__name__)
BACKGROUND_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="chat-run")
REGENERATE_BYPASS_CACHE = os.getenv("REGENERATE_BYPASS_CACHE", "0") == "1"


class ChatExecutionService:
    def __init__(self) -> None:
        self.chat_service = ChatService()
        self.run_service = RunService()
        self.conversation_resolver = ConversationResolver()

    def _workflow_result_to_metadata(self, result: dict, route_snapshot: dict, resolved_request: dict[str, Any] | None = None) -> dict:
        metadata = {
            "route": route_snapshot,
            "route_reason": result.get("route_reason", route_snapshot.get("reason", "")),
            "active_skill": result.get("active_skill") or result.get("skill_name") or "",
            "sql_query": result.get("sql_query", ""),
            "sql_error": result.get("sql_error", ""),
            "columns": result.get("table_columns") or [],
            "rows": result.get("db_result") or [],
            "row_count": result.get("row_count"),
            "truncated": bool(result.get("truncated")),
            "cache_hit": bool(result.get("cache_hit")),
        }
        if resolved_request:
            metadata["resolved_request"] = dict(resolved_request)
        return metadata

    def _build_route_snapshot(self, decision: RouteDecision) -> dict:
        return {
            "route": decision.route,
            "confidence": decision.confidence,
            "matched_domains": decision.matched_domains,
            "target_tables": decision.target_tables,
            "filters": decision.filters,
            "reason": decision.reason,
            "positive_hits": decision.positive_hits,
            "negative_hits": decision.negative_hits,
            "confidence_breakdown": decision.confidence_breakdown,
        }

    def _cacheable_result(self, workflow_result: dict) -> dict:
        return {
            "final_answer": workflow_result.get("final_answer") or "",
            "sql_query": workflow_result.get("sql_query") or "",
            "sql_error": workflow_result.get("sql_error") or "",
            "db_result": workflow_result.get("db_result") or [],
            "table_columns": workflow_result.get("table_columns") or [],
            "row_count": workflow_result.get("row_count"),
            "truncated": bool(workflow_result.get("truncated")),
            "active_skill": workflow_result.get("active_skill") or workflow_result.get("skill_name") or "",
            "route": workflow_result.get("route") or "",
            "route_reason": workflow_result.get("route_reason") or "",
        }

    def _publish_thread(self, thread_id: int, *, event: str) -> None:
        thread_event_publisher.publish_snapshot(thread_id, event=event)

    def _handle_workflow_event(self, db: Session, run: Run, thread: Thread, node: str, payload: dict) -> None:
        route = payload.get("route") if isinstance(payload, dict) else None
        route_reason = payload.get("route_reason") if isinstance(payload, dict) else None
        sql_query = payload.get("sql_query") if isinstance(payload, dict) else None
        sql_error = payload.get("sql_error") if isinstance(payload, dict) else None
        metrics_service.record_node_event(run.public_id, node=node, payload=payload if isinstance(payload, dict) else {})
        self.run_service.update_run_progress(
            db,
            run,
            current_step=node,
            route=route,
            route_reason=route_reason,
            sql_query=sql_query,
            error_message=sql_error,
        )
        thread.updated_at = utcnow()
        db.commit()
        self._publish_thread(thread.id, event=node)

    def _resolve_request_for_thread(self, db: Session, thread: Thread, question: str) -> dict[str, Any]:
        messages = self.run_service.repo.list_messages_for_thread(db, thread.id)
        return self.conversation_resolver.resolve(question=question, messages=messages)

    def _update_resolved_route(self, resolved_request: dict[str, Any] | None, route: str) -> dict[str, Any] | None:
        if not resolved_request:
            return None
        updated = dict(resolved_request)
        updated["resolved_route"] = route or updated.get("resolved_route") or updated.get("route_hint") or ""
        return updated

    def _user_message_metadata(self, resolved_request: dict[str, Any] | None = None) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        if resolved_request:
            metadata["resolved_request"] = dict(resolved_request)
        return metadata

    def _load_turn_request(self, db: Session, thread: Thread, turn: Turn, question: str) -> dict[str, Any]:
        metadata = getattr(turn.user_message, "metadata_dict", {}) or {}
        resolved_request = metadata.get("resolved_request") if isinstance(metadata, dict) else None
        if isinstance(resolved_request, dict) and resolved_request.get("resolved_question"):
            return dict(resolved_request)
        recomputed = self._resolve_request_for_thread(db, thread, question)
        if turn.user_message:
            self.run_service.update_message_metadata(db, turn.user_message, self._user_message_metadata(recomputed))
        return recomputed

    def execute_initial_turn(self, db: Session, thread: Thread, question: str) -> dict:
        turn, user_message, run = self.run_service.start_initial_run(db, thread, question)
        resolved_request = self._resolve_request_for_thread(db, thread, question)
        self.run_service.update_message_metadata(db, user_message, self._user_message_metadata(resolved_request))
        db.flush()
        return {
            "turn_id": turn.id,
            "user_message_id": user_message.id,
            "run_id": run.public_id,
            "status": run.status,
        }

    def execute_regenerate(self, db: Session, thread: Thread, assistant_message_id: int) -> dict | None:
        started = self.run_service.start_regenerate_run(db, thread, assistant_message_id)
        if not started:
            return None
        turn, run = started
        db.flush()
        return {
            "turn_id": turn.id,
            "run_id": run.public_id,
            "status": run.status,
        }

    def enqueue_initial_turn(self, thread_id: int, turn_id: int, run_id: str, question: str) -> None:
        BACKGROUND_EXECUTOR.submit(self._run_workflow_job, thread_id, turn_id, run_id, question)

    def enqueue_regenerate(self, thread_id: int, turn_id: int, run_id: str) -> None:
        BACKGROUND_EXECUTOR.submit(self._run_workflow_job, thread_id, turn_id, run_id, None)

    def _run_workflow_job(self, thread_id: int, turn_id: int, run_id: str, question: str | None) -> None:
        db = SessionLocal()
        try:
            thread = db.query(Thread).filter(Thread.id == thread_id).first()
            turn = db.query(Turn).filter(Turn.id == turn_id, Turn.thread_id == thread_id).first()
            run = db.query(Run).filter(Run.public_id == run_id, Run.thread_id == thread_id).first()
            if not thread or not turn or not run:
                return
            if run.status not in ACTIVE_RUN_STATUSES:
                return
            if question is None:
                question = turn.user_message.content if turn.user_message else ""
            resolved_request = self._load_turn_request(db, thread, turn, question)
            query_state = dict(resolved_request.get("query_state") or {})
            query_mode = str(resolved_request.get("mode") or "standalone_query")
            effective_question = str(query_state.get("query_text") or resolved_request.get("resolved_question") or question or "").strip()
            if not effective_question:
                effective_question = question or ""
            if self.run_service.is_cancel_requested(run):
                self.run_service.cancel_run(db, run, turn)
                thread.updated_at = utcnow()
                db.commit()
                metrics_service.mark_run_finished(run.public_id, status="cancelled", route=run.route)
                self._publish_thread(thread.id, event="cancelled")
                return
            self.run_service.mark_run_running(db, run, current_step="queued")
            thread.updated_at = utcnow()
            db.commit()
            self._publish_thread(thread.id, event="run_started")
            metrics_service.mark_run_started(run.public_id)
            history = self.chat_service.build_thread_history(db, thread)
            initial_decision = route_question_for_state(effective_question, query_state)
            resolved_request = self._update_resolved_route(resolved_request, initial_decision.route) or resolved_request
            if turn.user_message:
                self.run_service.update_message_metadata(db, turn.user_message, self._user_message_metadata(resolved_request))
                db.commit()
            metrics_service.mark_run_route(run.public_id, initial_decision.route)
            route_snapshot = self._build_route_snapshot(initial_decision)
            bypass_cache = REGENERATE_BYPASS_CACHE and run.kind == "regenerate"
            cache_key = ""
            if not bypass_cache:
                cache_key = query_cache_service.build_key(question=effective_question, decision=initial_decision)
                cached_result = query_cache_service.get(cache_key)
                if cached_result:
                    metrics_service.record_cache_hit()
                    cached_result["cache_hit"] = True
                    self.run_service.update_run_progress(
                        db,
                        run,
                        current_step="completed",
                        route=cached_result.get("route") or initial_decision.route,
                        route_reason=cached_result.get("route_reason") or initial_decision.reason,
                        sql_query=cached_result.get("sql_query", ""),
                        error_message=cached_result.get("sql_error", ""),
                    )
                    thread.updated_at = utcnow()
                    db.commit()
                    metadata = self._workflow_result_to_metadata(cached_result, route_snapshot, resolved_request)
                    answer = cached_result.get("final_answer") or f"[rewrite] 未生成最终回答：{effective_question}"
                    self.run_service.complete_run(db, run, turn, answer, metadata)
                    thread.updated_at = utcnow()
                    db.commit()
                    metrics_service.mark_run_finished(run.public_id, status="completed", route=initial_decision.route)
                    self._publish_thread(thread.id, event="run_finished")
                    return
                metrics_service.record_cache_miss()
            else:
                logger.info("cache bypassed for regenerate run_id={}", run.public_id)

            def is_cancelled() -> bool:
                check_db = SessionLocal()
                try:
                    queued_run = check_db.query(Run).filter(Run.public_id == run_id).first()
                    return self.run_service.is_cancel_requested(queued_run) if queued_run else False
                finally:
                    check_db.close()

            def on_event(node: str, payload: dict) -> None:
                event_db = SessionLocal()
                try:
                    event_run = event_db.query(Run).filter(Run.public_id == run_id, Run.thread_id == thread_id).first()
                    event_thread = event_db.query(Thread).filter(Thread.id == thread_id).first()
                    if not event_run or not event_thread:
                        return
                    self._handle_workflow_event(event_db, event_run, event_thread, node, payload or {})
                finally:
                    event_db.close()

            workflow_result = asyncio.run(
                execute_chat_workflow(
                    effective_question,
                    history,
                    initial_decision=initial_decision,
                    query_state=query_state,
                    query_mode=query_mode,
                    is_cancelled=is_cancelled,
                    on_event=on_event,
                )
            )
            db.refresh(run)
            db.refresh(turn)
            db.refresh(thread)
            if self.run_service.is_cancel_requested(run):
                self.run_service.cancel_run(db, run, turn)
                thread.updated_at = utcnow()
                db.commit()
                metrics_service.mark_run_finished(run.public_id, status="cancelled", route=initial_decision.route)
                self._publish_thread(thread.id, event="cancelled")
                return
            self.run_service.update_run_progress(
                db,
                run,
                current_step="completed",
                route=workflow_result.get("route", run.route),
                route_reason=workflow_result.get("route_reason", run.route_reason),
                sql_query=workflow_result.get("sql_query", ""),
                error_message=workflow_result.get("sql_error", ""),
            )
            thread.updated_at = utcnow()
            db.commit()
            db.refresh(run)
            db.refresh(turn)
            if self.run_service.is_cancel_requested(run):
                self.run_service.cancel_run(db, run, turn)
                metrics_service.mark_run_finished(run.public_id, status="cancelled", route=initial_decision.route)
            else:
                if (not bypass_cache) and cache_key and (not workflow_result.get("sql_error")):
                    query_cache_service.set(
                        key=cache_key,
                        value=self._cacheable_result(workflow_result),
                        route=initial_decision.route,
                    )
                resolved_request = self._update_resolved_route(
                    resolved_request,
                    workflow_result.get("route") or initial_decision.route,
                ) or resolved_request
                metadata = self._workflow_result_to_metadata(workflow_result, route_snapshot, resolved_request)
                answer = workflow_result.get("final_answer") or f"[rewrite] 未生成最终回答：{effective_question}"
                self.run_service.complete_run(db, run, turn, answer, metadata)
                metrics_service.mark_run_finished(
                    run.public_id,
                    status="completed",
                    route=workflow_result.get("route") or initial_decision.route,
                )
            thread.updated_at = utcnow()
            db.commit()
            self._publish_thread(thread.id, event="run_finished")
        except CancelledError:
            db.rollback()
            logger.bind(thread_id=thread_id, run_id=run_id).info("run workflow cancelled")
            recovery = SessionLocal()
            try:
                run = recovery.query(Run).filter(Run.public_id == run_id, Run.thread_id == thread_id).first()
                turn = recovery.query(Turn).filter(Turn.id == turn_id, Turn.thread_id == thread_id).first()
                if run and turn:
                    self.run_service.cancel_run(recovery, run, turn)
                    recovery.commit()
                    metrics_service.mark_run_finished(run.public_id, status="cancelled", route=run.route)
                    self._publish_thread(thread_id, event="cancelled")
            finally:
                recovery.close()
        except Exception as exc:
            db.rollback()
            logger.bind(thread_id=thread_id, turn_id=turn_id, run_id=run_id).exception("run workflow failed")
            recovery = SessionLocal()
            try:
                run = recovery.query(Run).filter(Run.public_id == run_id, Run.thread_id == thread_id).first()
                turn = recovery.query(Turn).filter(Turn.id == turn_id, Turn.thread_id == thread_id).first()
                thread = recovery.query(Thread).filter(Thread.id == thread_id).first()
                if run and turn:
                    self.run_service.fail_run(recovery, run, turn, str(exc))
                    if thread:
                        thread.updated_at = utcnow()
                    recovery.commit()
                    metrics_service.mark_run_finished(run.public_id, status="failed", route=run.route)
                    self._publish_thread(thread_id, event="failed")
            finally:
                recovery.close()
        finally:
            db.close()

    def cancel_active_run(self, db: Session, run: Run, turn: Turn) -> dict:
        cancel_requested = self.run_service.request_cancel(db, run, turn)
        if not cancel_requested:
            return {"run_id": run.public_id, "status": run.status}
        self._publish_thread(run.thread_id, event="cancelling")
        return {"run_id": run.public_id, "status": run.status}

    def current_run_view(self, run: Run) -> dict:
        return {
            "run_id": run.public_id,
            "status": run.status,
            "current_step": run.current_step,
            "sql_query": run.sql_query,
            "error_message": run.error_message,
        }
