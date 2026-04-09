# core/auth_db.py
import os
import logging
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("boe.auth")

# 读取你的数据库链接，如果没有配置，默认在本地生成一个 users.db 的 SQLite 文件专门存用户
DB_URI = os.getenv("DB_URI", "sqlite:///./users.db") 

engine = create_engine(DB_URI)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 定义用户表
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

# 自动建表，但不要让导入阶段因数据库暂不可达而直接崩溃。
try:
    Base.metadata.create_all(bind=engine)
except Exception as exc:
    logger.warning("Skip auth_db create_all during import: %s", exc)
