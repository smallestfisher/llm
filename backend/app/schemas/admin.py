from __future__ import annotations

import inspect

from pydantic import BaseModel, conlist, constr


PasswordStr = constr(min_length=8, max_length=128)
RoleNameStr = constr(strip_whitespace=True, min_length=1, max_length=50)
_CONLIST_PARAMS = set(inspect.signature(conlist).parameters)
if "min_length" in _CONLIST_PARAMS and "max_length" in _CONLIST_PARAMS:
    RoleList = conlist(RoleNameStr, min_length=1, max_length=10)
else:
    RoleList = conlist(RoleNameStr, min_items=1, max_items=10)


class PasswordChangeRequest(BaseModel):
    current_password: PasswordStr
    new_password: PasswordStr


class PasswordResetRequest(BaseModel):
    new_password: PasswordStr


class UserStatusRequest(BaseModel):
    is_active: bool


class UserRoleUpdateRequest(BaseModel):
    roles: RoleList
