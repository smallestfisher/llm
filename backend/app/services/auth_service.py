from __future__ import annotations

import bcrypt

from sqlalchemy.orm import Session

from app.bootstrap import hash_password
from app.models import Role, User, utcnow


class AuthService:
    def get_user_by_username(self, db: Session, username: str) -> User | None:
        return db.query(User).filter(User.username == username.strip()).first()

    def user_exists(self, db: Session, username: str) -> bool:
        return self.get_user_by_username(db, username) is not None

    def user_count(self, db: Session) -> int:
        return db.query(User).count()

    def default_roles_for_new_user(self, db: Session) -> list[str]:
        return ["admin", "user"] if self.user_count(db) == 0 else ["user"]

    def verify_password(self, password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

    def mark_login(self, db: Session, user: User) -> User:
        user.last_login_at = utcnow()
        db.flush()
        return user

    def create_user(self, db: Session, username: str, password: str, roles: list[str]) -> User:
        user = User(username=username.strip(), password_hash=hash_password(password), is_active=True)
        db.add(user)
        db.flush()
        role_rows = db.query(Role).filter(Role.name.in_(roles)).all()
        user.roles = role_rows
        db.flush()
        return user

    def is_active(self, user: User) -> bool:
        return bool(user.is_active)

    def role_names(self, user: User) -> list[str]:
        return [role.name for role in user.roles]
