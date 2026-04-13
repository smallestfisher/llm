from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Role, User


class UserRepository:
    def get_by_id(self, db: Session, user_id: int) -> User | None:
        return db.query(User).filter(User.id == user_id).first()

    def get_by_username(self, db: Session, username: str) -> User | None:
        return db.query(User).filter(User.username == username.strip()).first()

    def count(self, db: Session) -> int:
        return db.query(User).count()

    def list(self, db: Session) -> list[User]:
        return db.query(User).order_by(User.created_at.asc()).all()

    def get_roles(self, db: Session, names: list[str]) -> list[Role]:
        return db.query(Role).filter(Role.name.in_(names)).all()

    def save(self, db: Session, user: User) -> User:
        db.add(user)
        db.flush()
        return user
