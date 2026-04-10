import json
import os
import sqlite3
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from core.auth_db import (
    AuditLog,
    ChatThread,
    Role,
    SessionLocal,
    User,
    append_chat_message,
    build_seed_history,
    change_password,
    create_user,
    get_user_role_names,
    init_local_db,
    log_audit,
    set_user_roles,
    user_has_role,
    utcnow,
    verify_password,
)
from core.graph import get_workflow


SESSION_SECRET = os.getenv("SESSION_SECRET", "change-this-session-secret")
workflow = get_workflow()
templates = Jinja2Templates(directory="templates")


class ChatPayload(BaseModel):
    question: str


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_local_db()
    yield


app = FastAPI(title="BOE Data Copilot", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=60 * 60 * 12)
app.mount("/static", StaticFiles(directory="static"), name="static")


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def push_flash(request: Request, level: str, message: str) -> None:
    flashes = request.session.setdefault("_flashes", [])
    flashes.append({"level": level, "message": message})


def pop_flashes(request: Request) -> list[dict]:
    return request.session.pop("_flashes", [])


def current_user(request: Request, db: Session) -> Optional[User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        request.session.clear()
        return None
    return user


def require_user(request: Request, db: Session) -> User:
    user = current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user


def require_admin(request: Request, db: Session) -> User:
    user = require_user(request, db)
    if not user_has_role(user, "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return user


def role_names(user: Optional[User]) -> list[str]:
    return get_user_role_names(user)


def parse_roles(raw: str) -> list[str]:
    names = []
    for token in raw.replace("，", ",").split(","):
        name = token.strip().lower()
        if name and name not in names:
            names.append(name)
    return names or ["user"]


def has_any_user(db: Session) -> bool:
    return db.query(User.id).first() is not None


def is_last_active_admin(db: Session, user: User) -> bool:
    if not user_has_role(user, "admin") or not user.is_active:
        return False
    active_admins = (
        db.query(User)
        .join(User.roles)
        .filter(User.is_active.is_(True))
        .filter(Role.name == "admin")
        .count()
    )
    return active_admins <= 1


def get_thread_for_user(db: Session, user: User, public_id: str) -> Optional[ChatThread]:
    query = db.query(ChatThread).filter(ChatThread.public_id == public_id)
    if user_has_role(user, "admin"):
        return query.first()
    return query.filter(ChatThread.owner_id == user.id).first()


def list_threads(db: Session, user: User) -> list[ChatThread]:
    query = db.query(ChatThread)
    if not user_has_role(user, "admin"):
        query = query.filter(ChatThread.owner_id == user.id)
    return query.order_by(ChatThread.updated_at.desc()).all()


def create_thread(db: Session, user: User) -> ChatThread:
    thread = ChatThread(owner_id=user.id)
    db.add(thread)
    db.flush()
    return thread


def render_template(
    request: Request,
    template_name: str,
    db: Session,
    user: Optional[User],
    **context,
):
    threads = list_threads(db, user) if user else []
    template_context = {
        "request": request,
        "current_user": user,
        "current_roles": role_names(user),
        "is_admin": user_has_role(user, "admin") if user else False,
        "threads": threads,
        "flashes": pop_flashes(request),
    }
    template_context.update(context)
    return templates.TemplateResponse(request=request, name=template_name, context=template_context)


def redirect(url: str, status_code: int = status.HTTP_303_SEE_OTHER) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=status_code)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _thread_has_langgraph_checkpoint(thread_id: str, db_path: str = "langgraph_memory.db") -> bool:
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM checkpoints WHERE thread_id = ? LIMIT 1",
                (thread_id,),
            ).fetchone()
        return row is not None
    except sqlite3.Error:
        return False


async def run_chat_workflow(thread: ChatThread, question: str) -> dict:
    inputs = {"question": question}
    if not _thread_has_langgraph_checkpoint(thread.public_id):
        inputs["chat_history"] = build_seed_history(thread)
    config = {"configurable": {"thread_id": thread.public_id}}
    async with AsyncSqliteSaver.from_conn_string("langgraph_memory.db") as saver:
        engine = workflow.compile(checkpointer=saver)
        return await engine.ainvoke(inputs, config=config)


def _thinking_status_for_node(node_name: str) -> str:
    status_map = {
        "parse_query": "🔍 正在理解语义并识别查询目标...",
        "check_guard": "🛡️ 正在进行安全与合规检查...",
        "refine_filters": "🧭 正在整理过滤条件...",
        "get_schema": "🗂️ 正在装载相关表结构...",
        "write_sql": "✍️ 正在编写 SQL...",
        "execute_sql": "🚀 正在执行数据库查询...",
        "reflect_sql": "🔧 发现错误，正在修正 SQL...",
        "generate_answer": "🧠 正在组织最终回答...",
    }
    return status_map.get(node_name, "")


def _ndjson_line(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


def serialize_message(message) -> dict:
    return {
        "role": message.role,
        "content": message.content,
        "metadata": message.payload,
        "created_at": message.created_at.isoformat() if message.created_at else "",
    }


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    db = next(get_db())
    try:
        user = current_user(request, db)
        if user:
            return redirect("/")
        return render_template(
            request,
            "login.html",
            db,
            None,
            is_first_user=not has_any_user(db),
            auth_screen=True,
        )
    finally:
        db.close()


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    db = next(get_db())
    try:
        user = current_user(request, db)
        if user:
            return redirect("/")
        return render_template(
            request,
            "register.html",
            db,
            None,
            is_first_user=not has_any_user(db),
            auth_screen=True,
        )
    finally:
        db.close()


@app.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    db = next(get_db())
    try:
        if current_user(request, db):
            return redirect("/")

        normalized_username = username.strip()
        if not normalized_username:
            push_flash(request, "error", "用户名不能为空。")
            return redirect("/register")
        if len(password) < 8:
            push_flash(request, "error", "密码至少需要 8 位。")
            return redirect("/register")
        if password != confirm_password:
            push_flash(request, "error", "两次输入的密码不一致。")
            return redirect("/register")

        is_first_user = not has_any_user(db)
        role_names_for_user = ["admin", "user"] if is_first_user else ["user"]
        try:
            user = create_user(
                db,
                normalized_username,
                password,
                role_names=role_names_for_user,
            )
        except ValueError as exc:
            push_flash(request, "error", str(exc))
            return redirect("/register")

        request.session["user_id"] = user.id
        log_audit(
            db,
            action="register",
            actor=user,
            target_type="user",
            target_id=str(user.id),
            ip_address=client_ip(request),
            details={
                "username": user.username,
                "roles": role_names(user),
                "is_first_user": is_first_user,
            },
        )
        db.commit()

        if is_first_user:
            push_flash(request, "success", "首个注册账号已创建，并已授予管理员权限。")
        else:
            push_flash(request, "success", "注册成功，已使用新账号登录。")
        return redirect("/")
    finally:
        db.close()


@app.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    db = next(get_db())
    try:
        user = db.query(User).filter(User.username == username.strip()).first()
        if not user or not verify_password(password, user.password_hash):
            log_audit(
                db,
                action="login",
                actor=user,
                target_type="user",
                target_id=username.strip(),
                status="failed",
                ip_address=client_ip(request),
                details={"reason": "invalid_credentials"},
            )
            db.commit()
            push_flash(request, "error", "用户名或密码错误。")
            return redirect("/login")
        if not user.is_active:
            log_audit(
                db,
                action="login",
                actor=user,
                target_type="user",
                target_id=str(user.id),
                status="failed",
                ip_address=client_ip(request),
                details={"reason": "disabled"},
            )
            db.commit()
            push_flash(request, "error", "账号已被禁用。")
            return redirect("/login")

        user.last_login_at = utcnow()
        request.session["user_id"] = user.id
        log_audit(
            db,
            action="login",
            actor=user,
            target_type="user",
            target_id=str(user.id),
            ip_address=client_ip(request),
        )
        db.commit()
        return redirect("/")
    finally:
        db.close()


@app.post("/logout")
async def logout(request: Request):
    db = next(get_db())
    try:
        user = current_user(request, db)
        if user:
            log_audit(
                db,
                action="logout",
                actor=user,
                target_type="user",
                target_id=str(user.id),
                ip_address=client_ip(request),
            )
            db.commit()
        request.session.clear()
        return redirect("/login")
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    db = next(get_db())
    try:
        user = current_user(request, db)
        if not user:
            return redirect("/login")
        threads = list_threads(db, user)
        if not threads:
            thread = create_thread(db, user)
            log_audit(
                db,
                action="thread_create",
                actor=user,
                target_type="thread",
                target_id=thread.public_id,
                ip_address=client_ip(request),
            )
            db.commit()
            return redirect(f"/threads/{thread.public_id}")
        return redirect(f"/threads/{threads[0].public_id}")
    finally:
        db.close()


@app.get("/threads/new")
async def new_thread(request: Request):
    db = next(get_db())
    try:
        user = current_user(request, db)
        if not user:
            return redirect("/login")
        thread = create_thread(db, user)
        log_audit(
            db,
            action="thread_create",
            actor=user,
            target_type="thread",
            target_id=thread.public_id,
            ip_address=client_ip(request),
        )
        db.commit()
        return redirect(f"/threads/{thread.public_id}")
    finally:
        db.close()


@app.get("/threads/{public_id}", response_class=HTMLResponse)
async def thread_page(request: Request, public_id: str):
    db = next(get_db())
    try:
        user = current_user(request, db)
        if not user:
            return redirect("/login")
        thread = get_thread_for_user(db, user, public_id)
        if not thread:
            push_flash(request, "error", "对话不存在或无权访问。")
            return redirect("/")
        messages = [serialize_message(message) for message in thread.messages]
        return render_template(
            request,
            "chat.html",
            db,
            user,
            selected_thread=thread,
            messages=messages,
            hide_topbar=True,
            chat_layout=True,
        )
    finally:
        db.close()


@app.post("/api/chat/{public_id}")
async def chat_api(request: Request, public_id: str, payload: ChatPayload):
    db = next(get_db())
    try:
        user = current_user(request, db)
        if not user:
            return JSONResponse({"detail": "未登录"}, status_code=status.HTTP_401_UNAUTHORIZED)

        thread = get_thread_for_user(db, user, public_id)
        if not thread:
            return JSONResponse({"detail": "对话不存在"}, status_code=status.HTTP_404_NOT_FOUND)

        question = payload.question.strip()
        if not question:
            return JSONResponse({"detail": "问题不能为空"}, status_code=status.HTTP_400_BAD_REQUEST)

        append_chat_message(db, thread, "user", question)
        db.commit()
        user_id = user.id
        ip_address = client_ip(request)
        thread_public_id = thread.public_id
        thread_title = thread.title
    finally:
        db.close()

    async def event_stream():
        final_payload = None
        state_snapshot = {}
        try:
            yield _ndjson_line({"type": "status", "message": "正在启动工作流..."})
            inputs = {"question": question}
            db_history = SessionLocal()
            try:
                stream_thread = db_history.query(ChatThread).filter(ChatThread.public_id == thread_public_id).first()
                if stream_thread and not _thread_has_langgraph_checkpoint(thread_public_id):
                    inputs["chat_history"] = build_seed_history(stream_thread)
            finally:
                db_history.close()

            config = {"configurable": {"thread_id": thread_public_id}}
            async with AsyncSqliteSaver.from_conn_string("langgraph_memory.db") as saver:
                engine = workflow.compile(checkpointer=saver)
                async for output in engine.astream(inputs, config=config):
                    for node_name, node_output in output.items():
                        state_snapshot.update(node_output or {})
                        status_text = _thinking_status_for_node(node_name)
                        if status_text:
                            yield _ndjson_line({"type": "status", "node": node_name, "message": status_text})
                        if node_name == "generate_answer":
                            final_answer = node_output.get("final_answer", "")
                            metadata = {
                                "columns": state_snapshot.get("table_columns") or [],
                                "rows": state_snapshot.get("db_result") or [],
                                "row_count": state_snapshot.get("row_count"),
                                "truncated": bool(state_snapshot.get("truncated")),
                                "sql_query": state_snapshot.get("sql_query", ""),
                            }
                            final_payload = {
                                "type": "final",
                                "answer": final_answer,
                                "thread_id": thread_public_id,
                                "thread_title": thread_title,
                                "metadata": metadata,
                            }
                            yield _ndjson_line(final_payload)

            if final_payload:
                db_save = SessionLocal()
                try:
                    save_user = db_save.query(User).filter(User.id == user_id).first()
                    save_thread = db_save.query(ChatThread).filter(ChatThread.public_id == thread_public_id).first()
                    if save_thread:
                        append_chat_message(
                            db_save,
                            save_thread,
                            "assistant",
                            final_payload["answer"],
                            metadata=final_payload["metadata"],
                        )
                    log_audit(
                        db_save,
                        action="chat_query",
                        actor=save_user,
                        target_type="thread",
                        target_id=thread_public_id,
                        ip_address=ip_address,
                        details={"question": question[:120]},
                    )
                    db_save.commit()
                except Exception:
                    db_save.rollback()
                    raise
                finally:
                    db_save.close()
        except Exception as exc:
            error_message = f"处理出错：{exc}"
            db_error = SessionLocal()
            try:
                error_user = db_error.query(User).filter(User.id == user_id).first()
                error_thread = db_error.query(ChatThread).filter(ChatThread.public_id == thread_public_id).first()
                if error_thread:
                    append_chat_message(db_error, error_thread, "assistant", error_message)
                log_audit(
                    db_error,
                    action="chat_query",
                    actor=error_user,
                    target_type="thread",
                    target_id=thread_public_id,
                    status="failed",
                    ip_address=ip_address,
                    details={"question": question[:120], "error": str(exc)},
                )
                db_error.commit()
            except Exception:
                db_error.rollback()
            finally:
                db_error.close()
            yield _ndjson_line({"type": "error", "detail": error_message})

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@app.get("/profile/password", response_class=HTMLResponse)
async def password_page(request: Request):
    db = next(get_db())
    try:
        user = current_user(request, db)
        if not user:
            return redirect("/login")
        return render_template(
            request,
            "profile.html",
            db,
            user,
            hide_topbar=True,
            modal_layout=True,
        )
    finally:
        db.close()


@app.post("/profile/password")
async def password_submit(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
):
    db = next(get_db())
    try:
        user = current_user(request, db)
        if not user:
            return redirect("/login")
        if not verify_password(current_password, user.password_hash):
            push_flash(request, "error", "当前密码不正确。")
            return redirect("/profile/password")
        if len(new_password) < 8:
            push_flash(request, "error", "新密码至少需要 8 位。")
            return redirect("/profile/password")

        change_password(db, user, new_password)
        log_audit(
            db,
            action="password_change",
            actor=user,
            target_type="user",
            target_id=str(user.id),
            ip_address=client_ip(request),
        )
        db.commit()
        push_flash(request, "success", "密码已更新。")
        return redirect("/profile/password")
    finally:
        db.close()


@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request):
    db = next(get_db())
    try:
        user = current_user(request, db)
        if not user:
            return redirect("/login")
        if not user_has_role(user, "admin"):
            push_flash(request, "error", "需要管理员权限。")
            return redirect("/")
        user_rows = []
        for row in db.query(User).order_by(User.created_at.asc()).all():
            user_rows.append(
                {
                    "id": row.id,
                    "username": row.username,
                    "is_active": row.is_active,
                    "roles": role_names(row),
                    "created_at": row.created_at,
                    "last_login_at": row.last_login_at,
                }
            )
        return render_template(
            request,
            "admin_users.html",
            db,
            user,
            users=user_rows,
            fill_layout=True,
        )
    finally:
        db.close()


@app.post("/admin/users")
async def admin_create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    roles: str = Form("user"),
):
    db = next(get_db())
    try:
        admin = current_user(request, db)
        if not admin:
            return redirect("/login")
        if not user_has_role(admin, "admin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        if len(password) < 8:
            push_flash(request, "error", "密码至少需要 8 位。")
            return redirect("/admin/users")

        try:
            user = create_user(db, username.strip(), password, parse_roles(roles))
        except ValueError as exc:
            push_flash(request, "error", str(exc))
            return redirect("/admin/users")

        log_audit(
            db,
            action="user_create",
            actor=admin,
            target_type="user",
            target_id=str(user.id),
            ip_address=client_ip(request),
            details={"username": user.username, "roles": role_names(user)},
        )
        db.commit()
        push_flash(request, "success", f"已创建用户 {user.username}。")
        return redirect("/admin/users")
    finally:
        db.close()


@app.post("/admin/users/{user_id}/status")
async def admin_update_user_status(
    request: Request,
    user_id: int,
    is_active: str = Form(...),
):
    db = next(get_db())
    try:
        admin = current_user(request, db)
        if not admin:
            return redirect("/login")
        if not user_has_role(admin, "admin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            push_flash(request, "error", "用户不存在。")
            return redirect("/admin/users")

        target_active = is_active == "1"
        if not target_active and user.id == admin.id:
            push_flash(request, "error", "不能禁用当前登录的管理员账号。")
            return redirect("/admin/users")
        if not target_active and is_last_active_admin(db, user):
            push_flash(request, "error", "不能禁用最后一个启用中的管理员。")
            return redirect("/admin/users")

        user.is_active = target_active
        user.updated_at = utcnow()
        log_audit(
            db,
            action="user_status_change",
            actor=admin,
            target_type="user",
            target_id=str(user.id),
            ip_address=client_ip(request),
            details={"username": user.username, "is_active": target_active},
        )
        db.commit()
        push_flash(request, "success", f"已更新 {user.username} 的启用状态。")
        return redirect("/admin/users")
    finally:
        db.close()


@app.post("/admin/users/{user_id}/roles")
async def admin_update_user_roles(
    request: Request,
    user_id: int,
    roles: str = Form(...),
):
    db = next(get_db())
    try:
        admin = current_user(request, db)
        if not admin:
            return redirect("/login")
        if not user_has_role(admin, "admin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            push_flash(request, "error", "用户不存在。")
            return redirect("/admin/users")

        new_roles = parse_roles(roles)
        if user.id == admin.id and "admin" not in new_roles:
            push_flash(request, "error", "不能移除自己当前会话的管理员角色。")
            return redirect("/admin/users")
        if user_has_role(user, "admin") and "admin" not in new_roles and is_last_active_admin(db, user):
            push_flash(request, "error", "不能移除最后一个启用中的管理员角色。")
            return redirect("/admin/users")

        set_user_roles(db, user, new_roles)
        log_audit(
            db,
            action="user_roles_change",
            actor=admin,
            target_type="user",
            target_id=str(user.id),
            ip_address=client_ip(request),
            details={"username": user.username, "roles": new_roles},
        )
        db.commit()
        push_flash(request, "success", f"已更新 {user.username} 的角色。")
        return redirect("/admin/users")
    finally:
        db.close()


@app.post("/admin/users/{user_id}/password")
async def admin_reset_user_password(
    request: Request,
    user_id: int,
    new_password: str = Form(...),
):
    db = next(get_db())
    try:
        admin = current_user(request, db)
        if not admin:
            return redirect("/login")
        if not user_has_role(admin, "admin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            push_flash(request, "error", "用户不存在。")
            return redirect("/admin/users")
        if len(new_password) < 8:
            push_flash(request, "error", "密码至少需要 8 位。")
            return redirect("/admin/users")

        change_password(db, user, new_password)
        log_audit(
            db,
            action="user_password_reset",
            actor=admin,
            target_type="user",
            target_id=str(user.id),
            ip_address=client_ip(request),
            details={"username": user.username},
        )
        db.commit()
        push_flash(request, "success", f"已重置 {user.username} 的密码。")
        return redirect("/admin/users")
    finally:
        db.close()


@app.get("/admin/audit", response_class=HTMLResponse)
async def audit_logs_page(request: Request):
    db = next(get_db())
    try:
        user = current_user(request, db)
        if not user:
            return redirect("/login")
        if not user_has_role(user, "admin"):
            push_flash(request, "error", "需要管理员权限。")
            return redirect("/")
        audit_logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(300).all()
        audit_entries = []
        for entry in audit_logs:
            audit_entries.append(
                {
                    "id": entry.id,
                    "action": entry.action,
                    "target_type": entry.target_type,
                    "target_id": entry.target_id,
                    "status": entry.status,
                    "ip_address": entry.ip_address,
                    "details": entry.details,
                    "created_at": entry.created_at,
                    "username": entry.actor.username if entry.actor else "-",
                }
            )
        return render_template(
            request,
            "audit_logs.html",
            db,
            user,
            audit_entries=audit_entries,
            fill_layout=True,
        )
    finally:
        db.close()
