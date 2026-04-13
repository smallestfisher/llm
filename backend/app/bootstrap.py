from __future__ import annotations

import bcrypt

from app.db import Base, SessionLocal, engine
from app.models import Role, User


ROLE_DESCRIPTIONS = {
    "admin": "系统管理员",
    "user": "普通用户",
}


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def ensure_role(session, name: str) -> Role:
    role = session.query(Role).filter(Role.name == name).first()
    if role:
        return role
    role = Role(name=name, description=ROLE_DESCRIPTIONS.get(name, f"{name} role"))
    session.add(role)
    session.flush()
    return role


def init_backend_db() -> None:
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        ensure_role(session, "admin")
        ensure_role(session, "user")
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
