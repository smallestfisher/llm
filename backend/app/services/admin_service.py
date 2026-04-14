from __future__ import annotations

from sqlalchemy.orm import Session

from app.bootstrap import hash_password
from app.models import Role, User, utcnow


class AdminService:
    def list_users(self, db: Session) -> list[User]:
        return db.query(User).order_by(User.created_at.asc()).all()

    def get_user(self, db: Session, user_id: int) -> User | None:
        return db.query(User).filter(User.id == user_id).first()

    def require_admin(self, user: User) -> None:
        if "admin" not in [role.name for role in user.roles]:
            raise PermissionError("需要管理员权限")

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

    def update_roles(self, db: Session, user: User, role_names: list[str]) -> list[str]:
        roles = db.query(Role).filter(Role.name.in_(role_names)).all()
        user.roles = roles
        db.flush()
        return [role.name for role in user.roles]
