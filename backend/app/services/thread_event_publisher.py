from __future__ import annotations

from app.db import SessionLocal
from app.services.thread_event_service import thread_event_service
from app.services.thread_query_service import ThreadQueryService


class ThreadEventPublisher:
    def __init__(self) -> None:
        self.thread_query_service = ThreadQueryService()

    def publish_snapshot(self, thread_id: int, *, event: str) -> None:
        db = SessionLocal()
        try:
            snapshot = self.thread_query_service.get_thread_detail_by_id(db, thread_id)
            if not snapshot:
                return
            thread_event_service.publish(
                snapshot["public_id"],
                {
                    "event": event,
                    "thread": snapshot,
                },
            )
        finally:
            db.close()


thread_event_publisher = ThreadEventPublisher()
