from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from itsdangerous import URLSafeSerializer, BadSignature
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User


SESSION_SECRET = os.getenv("BACKEND_SESSION_SECRET", os.getenv("SESSION_SECRET", "change-this-session-secret"))
serializer = URLSafeSerializer(SESSION_SECRET, salt="boe-rewrite-auth")


def issue_token(user: User) -> str:
    return serializer.dumps({"user_id": user.id})


def parse_token(token: str) -> int | None:
    try:
        payload = serializer.loads(token)
    except BadSignature:
        return None
    user_id = payload.get("user_id")
    if not isinstance(user_id, int):
        return None
    return user_id


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    return authorization[len(prefix):].strip() or None


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> User:
    token = _extract_bearer(authorization)
    return get_current_user_by_token(token or "", db)


def get_current_user_by_token(token: str, db: Session) -> User:
    user_id = parse_token(token or "")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    return user
