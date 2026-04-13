from __future__ import annotations

from app.models import Thread


class ThreadQueryService:
    def list_thread_summaries(self, rows: list[Thread]) -> list[dict]:
        return [
            {
                "id": row.id,
                "public_id": row.public_id,
                "title": row.title,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in rows
        ]

    def get_thread_detail(self, thread: Thread) -> dict:
        messages = sorted(thread.messages, key=lambda row: (row.created_at, row.id))
        turns = sorted(thread.turns, key=lambda row: row.sequence)
        runs = sorted(thread.runs, key=lambda row: ((row.started_at.isoformat() if row.started_at else ''), row.id), reverse=True)
        return {
            "id": thread.id,
            "public_id": thread.public_id,
            "title": thread.title,
            "updated_at": thread.updated_at.isoformat() if thread.updated_at else None,
            "latest_run": self.latest_run(thread),
            "messages": [
                {
                    "id": row.id,
                    "turn_id": row.turn_id,
                    "role": row.role,
                    "content": row.content,
                    "metadata": row.metadata_dict,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in messages
            ],
            "turns": [
                {
                    "id": row.id,
                    "sequence": row.sequence,
                    "status": row.status,
                    "user_message_id": row.user_message_id,
                    "latest_assistant_message_id": row.latest_assistant_message_id,
                }
                for row in turns
            ],
            "runs": [
                {
                    "id": row.id,
                    "public_id": row.public_id,
                    "turn_id": row.turn_id,
                    "kind": row.kind,
                    "status": row.status,
                    "current_step": row.current_step,
                    "route": row.route,
                    "route_reason": row.route_reason,
                    "sql_query": row.sql_query,
                    "error_message": row.error_message,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                }
                for row in runs
            ],
        }

    def latest_run(self, thread: Thread) -> dict | None:
        if not thread.runs:
            return None
        row = sorted(thread.runs, key=lambda item: ((item.started_at.isoformat() if item.started_at else ''), item.id), reverse=True)[0]
        return {
            "public_id": row.public_id,
            "status": row.status,
            "current_step": row.current_step,
            "route": row.route,
            "route_reason": row.route_reason,
            "sql_query": row.sql_query,
            "error_message": row.error_message,
        }
