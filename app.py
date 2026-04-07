import os
import chainlit as cl
import chainlit.data as cl_data
import bcrypt
import time
import logging
import os

logger = logging.getLogger("boe.app")
logging.basicConfig(level=logging.INFO)
DEBUG_TRACE = os.getenv("DEBUG_TRACE", "0") == "1"

from core.auth_db import SessionLocal, User
from core.graph import create_backend_engine
from core.local_data import LocalSQLiteDataLayer # 🔴 引入咱们手写的数据层

# 🔴 注册本地数据层（此时前端左侧就会自动出现历史记录侧边栏）
cl_data._data_layer = LocalSQLiteDataLayer("chainlit_ui.db")

engine = create_backend_engine()

@cl.password_auth_callback
def auth_callback(username: str, password: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user: return None
        is_valid = bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8'))
        if is_valid: return cl.User(identifier=username, metadata={"role": user.role})
        return None 
    finally:
        db.close()

# 🔴 场景 A：新建聊天时
@cl.on_chat_start
async def on_chat_start():
    # Chainlit 会自动生成一个原生的 thread_id，把它抓下来当做大模型的记忆 ID
    cl.user_session.set("thread_id", cl.context.session.thread_id)
    
    user = cl.user_session.get("user")
    welcome_msg = f"你好，**{user.identifier}**！我是你的专属数据库助手。你想查点什么？"
    await cl.Message(content=welcome_msg).send()

# 🔴 场景 B：点击侧边栏恢复历史聊天时
@cl.on_chat_resume
async def on_chat_resume(thread: cl.types.ThreadDict):
    # 当用户点击左侧边栏的旧记录，把那个旧记录的 ID 传给大模型，接上从前的记忆！
    cl.user_session.set("thread_id", thread["id"])

@cl.on_message
async def on_message(message: cl.Message):
    inputs = {"question": message.content}

    # 提取当前的记忆 ID（优先用 session 里保存的 thread_id）
    thread_id = cl.user_session.get("thread_id") or cl.context.session.thread_id
    cl.user_session.set("thread_id", thread_id)
    config = {"configurable": {"thread_id": thread_id}}

    ui_msg = cl.Message(content="")
    await ui_msg.send()

    start_ts = time.monotonic()
    template_route = None
    try:
        for output in engine.stream(inputs, config=config):
            for node_name, node_output in output.items():
                if node_name == "extract_intent":
                    intent = node_output.get("intent")
                    confidence = node_output.get("intent_confidence")
                    filters = node_output.get("intent_filters")
                    if DEBUG_TRACE:
                        logger.info("intent=%s confidence=%s filters=%s", intent, confidence, filters)
                    async with cl.Step(name="Template Match", type="tool") as step:
                        step.output = (
                            f"intent: {intent}\n"
                            f"confidence: {confidence}\n"
                            f"filters: {filters}"
                        )
                if node_name == "refine_filters":
                    refined = node_output.get("refined_filters")
                    if refined:
                        async with cl.Step(name="Refined Filters", type="tool") as step:
                            step.output = f"{refined}"
                if node_name == "write_sql" and node_output.get("sql_query"):
                    sql_source = "LLM SQL"
                    template_route = sql_source
                    if DEBUG_TRACE:
                        logger.info("%s: %s", sql_source, node_output.get("sql_query"))
                    async with cl.Step(name=sql_source, type="tool") as step:
                        step.output = node_output["sql_query"]
                if node_name == "execute_sql":
                    async with cl.Step(name="DB Result (Preview)", type="tool") as step:
                        raw = node_output.get("db_result", "")
                        result_len = node_output.get("db_result_len")
                        row_count = node_output.get("row_count")
                        columns = node_output.get("columns")
                        if DEBUG_TRACE:
                            logger.info("db_result_len=%s", result_len)
                        preview = raw if isinstance(raw, str) else str(raw)
                        if len(preview) > 1200:
                            preview = preview[:1200] + "\n... (truncated)"
                        meta = []
                        if columns:
                            meta.append(f"columns: {columns}")
                        if row_count is not None:
                            meta.append(f"row_count: {row_count}")
                        if result_len is not None:
                            meta.append(f"raw_len: {result_len}")
                        meta_text = ("\n".join(meta) + "\n") if meta else ""
                        step.output = meta_text + preview
                if "final_answer" in node_output:
                    ui_msg.content = node_output["final_answer"]
                    await ui_msg.update()
    except Exception as e:
        ui_msg.content = f"⚠️ 抱歉，查询发生错误：\n```python\n{str(e)}\n```"
        await ui_msg.update()
    finally:
        elapsed_ms = int((time.monotonic() - start_ts) * 1000)
        async with cl.Step(name="Execution Summary", type="tool") as step:
            step.output = (
                f"route: {template_route or 'unknown'}\n"
                f"elapsed_ms: {elapsed_ms}"
            )
        if DEBUG_TRACE:
            logger.info("route=%s elapsed_ms=%s", template_route or "unknown", elapsed_ms)
