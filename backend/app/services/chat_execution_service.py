from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.logging_config import get_logger
from app.models import Run, Thread, Turn, utcnow
from app.services.cache_service import query_cache_service
from app.services.chat_service import ChatService
from app.services.metrics_service import metrics_service
from app.services.thread_event_publisher import thread_event_publisher
from app.services.run_service import ACTIVE_RUN_STATUSES, RunService
from app.workflow.disambiguation import resolve_clarification_reply
from app.workflow.executor import execute_chat_workflow
from app.workflow.router import route_question
from app.workflow.state import CancelledError, RouteDecision

logger = get_logger(__name__)
BACKGROUND_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="chat-run")


class ChatExecutionService:
    def __init__(self) -> None:
        self.chat_service = ChatService()
        self.run_service = RunService()

    def _workflow_result_to_metadata(self, result: dict, route_snapshot: dict) -> dict:
        return {
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
            "needs_clarification": bool(result.get("needs_clarification")),
            "clarification_question": result.get("clarification_question", ""),
            "clarification_options": result.get("clarification_options") or [],
            "clarification_type": result.get("clarification_type", ""),
            "clarification_context": result.get("clarification_context") or {},
        }

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

    def _latest_assistant_metadata(self, thread: Thread) -> dict:
        assistants = [row for row in thread.messages if row.role == "assistant"]
        if not assistants:
            return {}
        latest = sorted(assistants, key=lambda row: (row.created_at, row.id))[-1]
        return latest.metadata_dict

    def _resolve_clarification_reply(self, thread: Thread, question: str) -> str:
        metadata = self._latest_assistant_metadata(thread)
        return resolve_clarification_reply(metadata, question)

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

    def execute_initial_turn(self, db: Session, thread: Thread, question: str) -> dict:
        turn, user_message, run = self.run_service.start_initial_run(db, thread, question)
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
            question = self._resolve_clarification_reply(thread, question)
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
            initial_decision = route_question(question)
            metrics_service.mark_run_route(run.public_id, initial_decision.route)
            route_snapshot = self._build_route_snapshot(initial_decision)
            cache_key = query_cache_service.build_key(question=question, decision=initial_decision)
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
                metadata = self._workflow_result_to_metadata(cached_result, route_snapshot)
                answer = cached_result.get("final_answer") or f"[rewrite] 未生成最终回答：{question}"
                self.run_service.complete_run(db, run, turn, answer, metadata)
                thread.updated_at = utcnow()
                db.commit()
                metrics_service.mark_run_finished(run.public_id, status="completed", route=initial_decision.route)
                self._publish_thread(thread.id, event="run_finished")
                return
            metrics_service.record_cache_miss()

            def is_cancelled() -> bool:
                check_db = SessionLocal()
                try:
                    r = check_db.query(Run).filter(Run.public_id == run_id).first()
                    return self.run_service.is_cancel_requested(r) if r else False
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
                    question,
                    history,
                    initial_decision=initial_decision,
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
                if not workflow_result.get("sql_error") and not workflow_result.get("needs_clarification"):
                    query_cache_service.set(
                        key=cache_key,
                        value=self._cacheable_result(workflow_result),
                        route=initial_decision.route,
                    )
                metadata = self._workflow_result_to_metadata(workflow_result, route_snapshot)
                answer = workflow_result.get("final_answer") or f"[rewrite] 未生成最终回答：{question}"
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
