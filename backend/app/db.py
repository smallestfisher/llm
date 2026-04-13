from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "app_rewrite.db"
BACKEND_DB_URI = os.getenv("BACKEND_DB_URI", f"sqlite:///{DEFAULT_DB_PATH}")
CONNECT_ARGS = {"check_same_thread": False} if BACKEND_DB_URI.startswith("sqlite") else {}

engine = create_engine(BACKEND_DB_URI, connect_args=CONNECT_ARGS)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
