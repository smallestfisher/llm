from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, issue_token
from app.db import get_db
from app.models import Role, Thread, User
from app.schemas.admin import PasswordChangeRequest, PasswordResetRequest, UserRoleUpdateRequest, UserStatusRequest
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.chat import CancelRunRequest, RegenerateTurnRequest, SendMessageRequest
from app.services.admin_service import AdminService
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.chat_execution_service import ChatExecutionService
from app.services.thread_query_service import ThreadQueryService
from app.services.thread_service import ThreadService
from app.services.user_admin_query_service import UserAdminQueryService

router = APIRouter()
auth_service = AuthService()
admin_service = AdminService()
audit_service = AuditService()
thread_service = ThreadService()
thread_query_service = ThreadQueryService()
user_admin_query_service = UserAdminQueryService()
chat_execution_service = ChatExecutionService()


@router.get("/health")
def healthcheck() -> dict:
    return {"ok": True}


@router.post("/auth/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    existing = auth_service.get_user_by_username(db, payload.username)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    user_count = db.query(User).count()
    roles = ["admin", "user"] if user_count == 0 else ["user"]
    user = auth_service.create_user(db, payload.username, payload.password, roles)
    audit_service.log(db, actor_id=user.id, action="register", target_type="user", target_id=str(user.id), details={"roles": roles})
    db.commit()
    return {"id": user.id, "username": user.username, "roles": roles, "token": issue_token(user)}


@router.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = auth_service.get_user_by_username(db, payload.username)
    if not user or not auth_service.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")
    auth_service.mark_login(db, user)
    db.commit()
    return {
        "id": user.id,
        "username": user.username,
        "roles": [role.name for role in user.roles],
        "token": issue_token(user),
        "is_active": user.is_active,
    }


@router.get("/threads")
def list_threads(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = thread_service.list_threads_for_user(db, current_user.id)
    return thread_query_service.list_thread_summaries(rows)


@router.post("/threads")
def create_thread(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    thread = thread_service.create_thread(db, current_user.id)
    audit_service.log(db, actor_id=current_user.id, action="thread_create", target_type="thread", target_id=thread.public_id)
    db.commit()
    return {"id": thread.id, "public_id": thread.public_id, "title": thread.title}


@router.get("/threads/{public_id}")
def get_thread(public_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    thread = db.query(Thread).filter_by(public_id=public_id, owner_id=current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    return thread_query_service.get_thread_detail(thread)


@router.post("/threads/{public_id}/messages")
def append_message(
    public_id: str,
    payload: SendMessageRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    thread = db.query(Thread).filter_by(public_id=public_id, owner_id=current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    result = chat_execution_service.execute_initial_turn(db, thread, payload.question)
    background_tasks.add_task(chat_execution_service.enqueue_initial_turn, thread.id, result["turn_id"], result["run_id"], payload.question)
    audit_service.log(db, actor_id=current_user.id, action="turn_create", target_type="thread", target_id=thread.public_id, details={"turn_id": result["turn_id"], "run_id": result["run_id"]})
    db.commit()
    return {"thread_id": thread.public_id, **result}


@router.post("/threads/{public_id}/regenerate")
def regenerate_message(
    public_id: str,
    payload: RegenerateTurnRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    thread = db.query(Thread).filter_by(public_id=public_id, owner_id=current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    result = chat_execution_service.execute_regenerate(db, thread, int(payload.assistant_message_id))
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到可重新生成的回复")
    background_tasks.add_task(chat_execution_service.enqueue_regenerate, thread.id, result["turn_id"], result["run_id"])
    audit_service.log(db, actor_id=current_user.id, action="turn_regenerate", target_type="thread", target_id=thread.public_id, details={"turn_id": result["turn_id"], "run_id": result["run_id"]})
    db.commit()
    return {"thread_id": thread.public_id, **result}


@router.delete("/threads/{public_id}")
def delete_thread(public_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    thread = db.query(Thread).filter_by(public_id=public_id, owner_id=current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    thread_service.delete_thread(db, thread)
    audit_service.log(db, actor_id=current_user.id, action="thread_delete", target_type="thread", target_id=public_id)
    db.commit()
    return {"ok": True, "public_id": public_id}


@router.post("/threads/{public_id}/runs/cancel")
def cancel_run(public_id: str, payload: CancelRunRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    thread = db.query(Thread).filter_by(public_id=public_id, owner_id=current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")
    run = next((row for row in thread.runs if row.public_id == payload.run_id), None)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="运行不存在")
    turn = next((row for row in thread.turns if row.id == run.turn_id), None)
    if not turn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="轮次不存在")
    result = chat_execution_service.cancel_active_run(db, run, turn)
    audit_service.log(db, actor_id=current_user.id, action="run_cancel", target_type="thread", target_id=thread.public_id, details={"run_id": run.public_id})
    db.commit()
    return {"ok": True, **result}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)) -> dict:
    return {
        "id": current_user.id,
        "username": current_user.username,
        "roles": [role.name for role in current_user.roles],
        "is_active": current_user.is_active,
        "token": issue_token(current_user),
    }


@router.post("/me/password")
def change_password(payload: PasswordChangeRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if not auth_service.verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码不正确")
    admin_service.change_password(db, current_user, payload.new_password)
    audit_service.log(db, actor_id=current_user.id, action="password_change", target_type="user", target_id=str(current_user.id))
    db.commit()
    return {"ok": True}


@router.get("/admin/users")
def admin_users(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if "admin" not in [role.name for role in current_user.roles]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return {"items": user_admin_query_service.list_users(db)}


@router.post("/admin/users/{user_id}/status")
def admin_user_status(user_id: int, payload: UserStatusRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if "admin" not in [role.name for role in current_user.roles]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    admin_service.set_user_active(db, user, payload.is_active)
    audit_service.log(db, actor_id=current_user.id, action="user_status_update", target_type="user", target_id=str(user.id), details={"is_active": user.is_active})
    db.commit()
    return {"ok": True, "is_active": user.is_active}


@router.post("/admin/users/{user_id}/password")
def admin_reset_password(user_id: int, payload: PasswordResetRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if "admin" not in [role.name for role in current_user.roles]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    admin_service.reset_password(db, user, payload.new_password)
    audit_service.log(db, actor_id=current_user.id, action="admin_password_reset", target_type="user", target_id=str(user.id))
    db.commit()
    return {"ok": True}


@router.post("/admin/users/{user_id}/roles")
def admin_update_roles(user_id: int, payload: UserRoleUpdateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if "admin" not in [role.name for role in current_user.roles]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    roles = db.query(Role).filter(Role.name.in_(payload.roles)).all()
    user.roles = roles
    audit_service.log(db, actor_id=current_user.id, action="user_roles_update", target_type="user", target_id=str(user.id), details={"roles": payload.roles})
    db.commit()
    return {"ok": True, "roles": [role.name for role in user.roles]}


@router.get("/admin/audits")
def admin_audits(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if "admin" not in [role.name for role in current_user.roles]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return {"items": user_admin_query_service.list_audits(db)}
