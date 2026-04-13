from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.audit_repository import AuditRepository


class AuditService:
    def __init__(self) -> None:
        self.repo = AuditRepository()

    def log(self, db: Session, **kwargs):
        return self.repo.create(db, **kwargs)
