from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import AuditLog


class AuditRepository:
    def create(
        self,
        db: Session,
        *,
        actor_id: int | None,
        action: str,
        target_type: str,
        target_id: str,
        status: str = "success",
        ip_address: str = "",
        details: dict | None = None,
    ) -> AuditLog:
        row = AuditLog(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            status=status,
            ip_address=ip_address,
            details_json=json.dumps(details or {}, ensure_ascii=False),
        )
        db.add(row)
        db.flush()
        return row
