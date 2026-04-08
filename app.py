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
from core.graph import get_workflow
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from core.local_data import LocalSQLiteDataLayer

# 🔴 注册本地数据层（此时前端左侧就会自动出现历史记录侧边栏）
cl_data._data_layer = LocalSQLiteDataLayer("chainlit_ui.db")

workflow = get_workflow()

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
    cl.user_session.set("thread_id", cl.context.session.thread_id)
    user = cl.user_session.get("user")
    welcome_msg = f"你好，**{user.identifier}**！我是 BOE 数据副驾驶 V2.0。\n已接入 12 张核心业务表，为您提供生产全链路决策支持。"
    await cl.Message(content=welcome_msg).send()


# 🔴 场景 B：点击侧边栏恢复历史聊天时
@cl.on_chat_resume
async def on_chat_resume(thread: cl.types.ThreadDict):
    # 当用户点击左侧边栏的旧记录，把那个旧记录的 ID 传给大模型，接上从前的记忆！
    cl.user_session.set("thread_id", thread["id"])

@cl.on_message
async def on_message(message: cl.Message):
    inputs = {"question": message.content}
    thread_id = cl.user_session.get("thread_id") or cl.context.session.thread_id
    cl.user_session.set("thread_id", thread_id)
    config = {"configurable": {"thread_id": thread_id}}

    # 创建一个统一的思考消息框
    thinking_msg = cl.Message(content="🤔 AI 正在思考...", author="Thinking")
    await thinking_msg.send()

    try:
        async with AsyncSqliteSaver.from_conn_string("langgraph_memory.db") as saver:
            engine = workflow.compile(checkpointer=saver)
            
            # 使用列表存储思维过程，以便最后汇总展示
            thought_text = ""
            
            async for output in engine.astream(inputs, config=config):
                for node_name, node_output in output.items():
                    # 动态更新思考状态
                    status_map = {
                        "normalize_question": "🔍 正在理解意图...",
                        "extract_intent": "🎯 正在识别查询目标...",
                        "write_sql": "✍️ 正在编写 SQL...",
                        "execute_sql": "🚀 正在数据库执行...",
                        "reflect_sql": "🔧 发现错误，正在修正 SQL..."
                    }
                    if node_name in status_map:
                        thinking_msg.content = f"🤔 {status_map[node_name]}"
                        await thinking_msg.update()
                    
                    # 获取最终回答
                    if node_name == "generate_answer":
                        final_answer = node_output.get("final_answer", "")
                        thinking_msg.content = "✅ 思考完成。"
                        await thinking_msg.update()
                        
                        # 发送最终结果
                        await cl.Message(content=final_answer).send()

    except Exception as e:
        thinking_msg.content = f"⚠️ 处理出错: {str(e)}"
        await thinking_msg.update()

