from __future__ import annotations

from sqlalchemy.orm import Session

from app.bootstrap import hash_password
from app.models import User, utcnow


class AdminService:
    def list_users(self, db: Session) -> list[User]:
        return db.query(User).order_by(User.created_at.asc()).all()

    def set_user_active(self, db: Session, user: User, is_active: bool) -> User:
        user.is_active = is_active
        user.updated_at = utcnow()
        db.flush()
        return user

    def reset_password(self, db: Session, user: User, new_password: str) -> User:
        user.password_hash = hash_password(new_password)
        user.updated_at = utcnow()
        db.flush()
        return user

    def change_password(self, db: Session, user: User, new_password: str) -> User:
        user.password_hash = hash_password(new_password)
        user.updated_at = utcnow()
        db.flush()
        return user
