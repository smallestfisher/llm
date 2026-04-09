# manage_users.py
import bcrypt
from core.auth_db import SessionLocal, User
import sys

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def add_user(username, password):
    db = SessionLocal()
    if db.query(User).filter(User.username == username).first():
        print(f"❌ 用户 {username} 已存在！")
        return
    
    new_user = User(
        username=username,
        password_hash=hash_password(password),
    )
    db.add(new_user)
    db.commit()
    print(f"✅ 成功添加用户: {username}")
    db.close()

def delete_user(username):
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    if not user:
        print(f"❌ 找不到用户 {username}")
        return
    
    db.delete(user)
    db.commit()
    print(f"✅ 成功删除用户: {username}")
    db.close()

def list_users():
    db = SessionLocal()
    users = db.query(User).all()
    print("\n=== 当前用户列表 ===")
    for u in users:
        print(f"ID: {u.id} | 用户名: {u.username}")
    print("====================\n")
    db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python manage_users.py [add|delete|list]")
        sys.exit(1)
        
    action = sys.argv[1]
    
    if action == "add":
        u = input("请输入新用户名: ")
        p = input("请输入新密码: ")
        add_user(u, p)
    elif action == "delete":
        u = input("请输入要删除的用户名: ")
        delete_user(u)
    elif action == "list":
        list_users()
    else:
        print("未知命令")
