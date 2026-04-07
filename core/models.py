# core/database.py (或者新建一个 models.py)
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DB_URI = os.getenv("DB_URI")
engine = create_engine(DB_URI)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 定义用户表
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)  # 存加密后的密码
    role = Column(String(20), default="user")            # user 或 admin

# 运行这行代码会在 MySQL 中自动建表（如果表不存在的话）
Base.metadata.create_all(bind=engine)
