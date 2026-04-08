import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


class Database:
    def __init__(self, uri: str):
        self.engine = create_engine(uri)

    def run(self, sql: str):
        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            if not result.returns_rows:
                return [], []
            columns = list(result.keys())
            if not columns:
                cursor = getattr(result, "cursor", None)
                description = getattr(cursor, "description", None) if cursor is not None else None
                if description:
                    columns = [d[0] for d in description if d and d[0]]
            rows = result.fetchall()
            return [tuple(row) for row in rows], columns


def get_db_connection() -> Database:
    """初始化并返回数据库连接（SQLAlchemy Engine Wrapper）"""
    db_uri = os.getenv("DB_URI")
    if not db_uri:
        raise ValueError("请在 .env 文件中配置 DB_URI")
    try:
        return Database(db_uri)
    except Exception as e:
        print(f"数据库连接失败: {e}")
        raise e
