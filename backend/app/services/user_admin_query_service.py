from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLog, User


class UserAdminQueryService:
    def list_users(self, db: Session) -> list[dict]:
        rows = db.query(User).order_by(User.created_at.asc()).all()
        return [
            {
                "id": row.id,
                "username": row.username,
                "roles": [role.name for role in row.roles],
                "is_active": row.is_active,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "last_login_at": row.last_login_at.isoformat() if row.last_login_at else None,
            }
            for row in rows
        ]

    def list_audits(self, db: Session) -> list[dict]:
        rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
        return [
            {
                "id": row.id,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "status": row.status,
                "ip_address": row.ip_address,
                "details": row.details,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "actor_username": row.actor.username if row.actor else None,
            }
            for row in rows
        ]
