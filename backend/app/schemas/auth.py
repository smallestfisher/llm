from __future__ import annotations

import inspect

from pydantic import BaseModel, conlist, constr


UsernameStr = constr(strip_whitespace=True, min_length=3, max_length=50)
PasswordStr = constr(min_length=8, max_length=128)
RoleNameStr = constr(strip_whitespace=True, min_length=1, max_length=50)
_CONLIST_PARAMS = set(inspect.signature(conlist).parameters)
if "min_length" in _CONLIST_PARAMS and "max_length" in _CONLIST_PARAMS:
    RoleList = conlist(RoleNameStr, min_length=1, max_length=10)
else:
    RoleList = conlist(RoleNameStr, min_items=1, max_items=10)


class RegisterRequest(BaseModel):
    username: UsernameStr
    password: PasswordStr


class LoginRequest(BaseModel):
    username: UsernameStr
    password: PasswordStr


class PasswordChangeRequest(BaseModel):
    current_password: PasswordStr
    new_password: PasswordStr


class PasswordResetRequest(BaseModel):
    new_password: PasswordStr


class UserStatusRequest(BaseModel):
    is_active: bool


class UserRoleUpdateRequest(BaseModel):
    roles: RoleList


class AuthResponse(BaseModel):
    id: int
    username: str
    roles: list[str]
    token: str


class MeResponse(BaseModel):
    id: int
    username: str
    roles: list[str]
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
