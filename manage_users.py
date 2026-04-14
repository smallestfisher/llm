import argparse

from app.bootstrap import ensure_role, hash_password, init_backend_db
from app.db import SessionLocal
from app.models import AuditLog, Role, User, utcnow


init_backend_db()


def get_user(db, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_user_role_names(user: User | None) -> list[str]:
    if not user:
        return []
    return sorted(role.name for role in user.roles)


def log_audit(
    db,
    *,
    action: str,
    target_type: str,
    target_id: str,
    details: dict | None = None,
    actor_id: int | None = None,
    status: str = "success",
    ip_address: str = "",
) -> AuditLog:
    row = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id or ""),
        status=status,
        ip_address=ip_address,
        details_json=__import__("json").dumps(details or {}, ensure_ascii=False),
    )
    db.add(row)
    db.flush()
    return row


def set_user_roles(db, user: User, role_names: list[str]) -> None:
    names: list[str] = []
    for role_name in role_names:
        name = (role_name or "").strip().lower()
        if name and name not in names:
            names.append(name)
    if not names:
        names = ["user"]
    user.roles = [ensure_role(db, name) for name in names]
    user.updated_at = utcnow()
    db.flush()


def create_user(db, username: str, password: str, role_names: list[str]) -> User:
    existing = get_user(db, username.strip())
    if existing:
        raise ValueError(f"用户 {username} 已存在")
    user = User(username=username.strip(), password_hash=hash_password(password), is_active=True)
    db.add(user)
    db.flush()
    set_user_roles(db, user, role_names)
    db.flush()
    return user


def change_password(db, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    user.updated_at = utcnow()
    db.flush()


def cmd_add(args) -> None:
    db = SessionLocal()
    try:
        user = create_user(db, args.username, args.password, args.roles.split(","))
        log_audit(
            db,
            action="cli_user_create",
            target_type="user",
            target_id=str(user.id),
            details={"username": user.username, "roles": get_user_role_names(user)},
        )
        db.commit()
        print(f"已创建用户: {user.username} roles={','.join(get_user_role_names(user))}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cmd_list(_: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        print("ID | 用户名 | 状态 | 角色")
        for user in db.query(User).order_by(User.id.asc()).all():
            status = "启用" if user.is_active else "禁用"
            print(f"{user.id} | {user.username} | {status} | {','.join(get_user_role_names(user))}")
    finally:
        db.close()


def cmd_set_active(args) -> None:
    db = SessionLocal()
    try:
        user = get_user(db, args.username)
        if not user:
            raise ValueError(f"用户不存在: {args.username}")
        user.is_active = args.active
        user.updated_at = utcnow()
        log_audit(
            db,
            action="cli_user_status_change",
            target_type="user",
            target_id=str(user.id),
            details={"username": user.username, "is_active": args.active},
        )
        db.commit()
        print(f"已更新状态: {user.username} -> {'启用' if args.active else '禁用'}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cmd_set_roles(args) -> None:
    db = SessionLocal()
    try:
        user = get_user(db, args.username)
        if not user:
            raise ValueError(f"用户不存在: {args.username}")
        set_user_roles(db, user, args.roles.split(","))
        log_audit(
            db,
            action="cli_user_roles_change",
            target_type="user",
            target_id=str(user.id),
            details={"username": user.username, "roles": get_user_role_names(user)},
        )
        db.commit()
        print(f"已更新角色: {user.username} -> {','.join(get_user_role_names(user))}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cmd_reset_password(args) -> None:
    db = SessionLocal()
    try:
        user = get_user(db, args.username)
        if not user:
            raise ValueError(f"用户不存在: {args.username}")
        change_password(db, user, args.password)
        log_audit(
            db,
            action="cli_user_password_reset",
            target_type="user",
            target_id=str(user.id),
            details={"username": user.username},
        )
        db.commit()
        print(f"已重置密码: {user.username}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="本地用户管理工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="创建用户")
    add_parser.add_argument("username")
    add_parser.add_argument("password")
    add_parser.add_argument("--roles", default="user")
    add_parser.set_defaults(func=cmd_add)

    list_parser = subparsers.add_parser("list", help="列出用户")
    list_parser.set_defaults(func=cmd_list)

    disable_parser = subparsers.add_parser("disable", help="禁用用户")
    disable_parser.add_argument("username")
    disable_parser.set_defaults(func=lambda args: cmd_set_active(argparse.Namespace(username=args.username, active=False)))

    enable_parser = subparsers.add_parser("enable", help="启用用户")
    enable_parser.add_argument("username")
    enable_parser.set_defaults(func=lambda args: cmd_set_active(argparse.Namespace(username=args.username, active=True)))

    roles_parser = subparsers.add_parser("roles", help="更新角色")
    roles_parser.add_argument("username")
    roles_parser.add_argument("roles")
    roles_parser.set_defaults(func=cmd_set_roles)

    password_parser = subparsers.add_parser("reset-password", help="重置密码")
    password_parser.add_argument("username")
    password_parser.add_argument("password")
    password_parser.set_defaults(func=cmd_reset_password)

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
