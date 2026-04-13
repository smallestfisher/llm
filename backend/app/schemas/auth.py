from __future__ import annotations

from pydantic import BaseModel


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class PasswordResetRequest(BaseModel):
    new_password: str


class UserStatusRequest(BaseModel):
    is_active: bool


class UserRoleUpdateRequest(BaseModel):
    roles: list[str]


class AuthResponse(BaseModel):
    id: int
    username: str
    roles: list[str]
    token: str


class MeResponse(AuthResponse):
    is_active: bool


class UserSummaryResponse(BaseModel):
    id: int
    username: str
    roles: list[str]
    is_active: bool
    created_at: str | None = None
    last_login_at: str | None = None


class AuditLogResponse(BaseModel):
    id: int
    action: str
    target_type: str
    target_id: str
    status: str
    ip_address: str
    details: dict
    created_at: str | None = None
    actor_username: str | None = None


class UserListResponse(BaseModel):
    items: list[UserSummaryResponse]


class AuditListResponse(BaseModel):
    items: list[AuditLogResponse]


class MutationResponse(BaseModel):
    ok: bool


class RoleMutationResponse(MutationResponse):
    roles: list[str]


class ActiveMutationResponse(MutationResponse):
    is_active: bool
