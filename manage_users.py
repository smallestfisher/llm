import argparse

from core.auth_db import (
    SessionLocal,
    User,
    change_password,
    create_user,
    get_user_role_names,
    log_audit,
    set_user_roles,
)


def get_user(db, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


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
