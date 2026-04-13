from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Run, Thread, Turn, utcnow
from app.services.chat_service import ChatService
from app.services.run_service import ACTIVE_RUN_STATUSES, RunService
from app.workflow.executor import execute_chat_workflow

logger = logging.getLogger(__name__)
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
        }

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
            if self.run_service.is_cancel_requested(run):
                self.run_service.cancel_run(db, run, turn)
                thread.updated_at = utcnow()
                db.commit()
                return
            self.run_service.mark_run_running(db, run, current_step="route")
            route_snapshot = self.chat_service.attach_route_to_run(run, question)
            thread.updated_at = utcnow()
            db.commit()
            history = self.chat_service.build_thread_history(db, thread)
            self.run_service.update_run_progress(db, run, current_step="workflow")
            thread.updated_at = utcnow()
            db.commit()
            workflow_result = asyncio.run(execute_chat_workflow(question, history))
            db.refresh(run)
            db.refresh(turn)
            db.refresh(thread)
            if self.run_service.is_cancel_requested(run):
                self.run_service.cancel_run(db, run, turn)
                thread.updated_at = utcnow()
                db.commit()
                return
            self.run_service.update_run_progress(
                db,
                run,
                current_step="answer",
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
            else:
                metadata = self._workflow_result_to_metadata(workflow_result, route_snapshot)
                answer = workflow_result.get("final_answer") or f"[rewrite] 未生成最终回答：{question}"
                self.run_service.complete_run(db, run, turn, answer, metadata)
            thread.updated_at = utcnow()
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.exception("run workflow failed", extra={"thread_id": thread_id, "turn_id": turn_id, "run_id": run_id})
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
            finally:
                recovery.close()
        finally:
            db.close()

    def cancel_active_run(self, db: Session, run: Run, turn: Turn) -> dict:
        cancel_requested = self.run_service.request_cancel(db, run, turn)
        if not cancel_requested:
            return {"run_id": run.public_id, "status": run.status}
        return {"run_id": run.public_id, "status": run.status}

    def current_run_view(self, run: Run) -> dict:
        return {
            "run_id": run.public_id,
            "status": run.status,
            "current_step": run.current_step,
            "sql_query": run.sql_query,
            "error_message": run.error_message,
        }
