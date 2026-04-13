from __future__ import annotations

from pydantic import BaseModel


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class PasswordResetRequest(BaseModel):
    new_password: str


class UserStatusRequest(BaseModel):
    is_active: bool


class UserRoleUpdateRequest(BaseModel):
    roles: list[str]
