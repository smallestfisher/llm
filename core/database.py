import os
from langchain_community.utilities import SQLDatabase
from dotenv import load_dotenv

load_dotenv()

def get_db_connection() -> SQLDatabase:
    """初始化并返回 LangChain 的 SQLDatabase 对象"""
    db_uri = os.getenv("DB_URI")
    if not db_uri:
        raise ValueError("请在 .env 文件中配置 DB_URI")
    
    # 定义你要给大模型看的业务表（排除业务无关的 users 表）
    target_tables = [
        "daily_inventory",
        "daily_schedule",
        "monthly_plan_approved",
        "oms_inventory",
        "p_demand",
        "product_attributes",
        "product_mapping",
        "production_actuals",
        "sales_financial_perf",
        "v_demand",
        "weekly_rolling_plan",
        "work_in_progress",
    ]
    
    # sample_rows_in_table_info=3 代表把表里的前3行数据给大模型看，极大提高SQL准确率
    try:
        db = SQLDatabase.from_uri(
            db_uri,
            include_tables=target_tables,
            sample_rows_in_table_info=3 
        )
        return db
    except Exception as e:
        print(f"数据库连接失败: {e}")
        raise e
