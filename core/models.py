"""Compatibility exports for legacy imports.

The canonical user/auth model lives in core.auth_db.
"""

from core.auth_db import Base, DB_URI, SessionLocal, User, engine

__all__ = ["Base", "DB_URI", "SessionLocal", "User", "engine"]
