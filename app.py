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
    
    actions = [
        cl.Action(name="quick_inventory", value="查询目前各工厂库存预警情况", label="🚨 库存预警", description="查看缺口情况"),
        cl.Action(name="quick_production", value="分析本月各工厂的计划达成率", label="📈 计划达成率", description="对比计划与实绩"),
        cl.Action(name="quick_wip", value="分析当前 WIP 在各工序的分布瓶颈", label="🏭 WIP分布", description="查找堵塞点")
    ]
    
    welcome_msg = f"你好，**{user.identifier}**！我是 BOE 数据副驾驶 V2.0。\n已接入 12 张核心业务表，为您提供生产全链路决策支持。"
    await cl.Message(content=welcome_msg, actions=actions).send()

@cl.on_action("quick_inventory")
@cl.on_action("quick_production")
@cl.on_action("quick_wip")
async def on_action(action):
    await cl.Message(content=f"已触发快捷查询：{action.value}").send()
    # 模拟用户发送消息
    await on_message(cl.Message(content=action.value))

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

    ui_msg = cl.Message(content="正在处理您的请求...")
    await ui_msg.send()

    start_ts = time.monotonic()
    try:
        async with AsyncSqliteSaver.from_conn_string("langgraph_memory.db") as saver:
            # 现场编译引擎
            engine = workflow.compile(checkpointer=saver)
            
            async for output in engine.astream(inputs, config=config):
                for node_name, node_output in output.items():
                    # 为每个节点创建一个 Step (思维链展示)
                    step_name = {
                        "normalize_question": "🔍 问题归一化",
                        "extract_intent": "🎯 意图识别",
                        "refine_filters": "🛠️ 规则补全",
                        "get_schema": "📚 加载表结构",
                        "write_sql": "✍️ 生成 SQL",
                        "execute_sql": "🚀 执行查询",
                        "reflect_sql": "🔧 SQL 纠错反思",
                        "generate_answer": "📝 组织语言"
                    }.get(node_name, node_name)

                    async with cl.Step(name=step_name) as step:
                        # 根据不同节点输出不同的详细信息
                        if node_name == "extract_intent":
                            step.output = f"识别到意图: {node_output.get('intent')}\n置信度: {node_output.get('intent_confidence')}"
                        elif node_name == "get_schema":
                            schema_len = len(node_output.get("table_schema", ""))
                            step.output = f"已加载相关表结构 (约 {schema_len} 字符)"
                        elif node_name == "write_sql":
                            step.output = f"```sql\n{node_output.get('sql_query')}\n```"
                        elif node_name == "execute_sql":
                            if node_output.get("sql_error"):
                                step.output = f"❌ 执行失败: {node_output.get('sql_error')}"
                            else:
                                res_len = len(str(node_output.get("db_result", "")))
                                step.output = f"✅ 查询成功，返回数据长度: {res_len}"
                        elif node_name == "reflect_sql":
                            step.output = f"⚠️ 发现错误，正在进行第 {node_output.get('retry_count')} 次修正...\n错误原因: {node_output.get('sql_error')}"
                        elif node_name == "generate_answer":
                            step.output = "正在生成自然语言回答并渲染可视化..."
                            final_answer = node_output.get("final_answer", "")
                            chart_json = node_output.get("chart_data")

                            # 如果有图表数据，渲染 Plotly 图表
                            if chart_json:
                                import plotly.io as pio
                                fig = pio.from_json(chart_json)
                                await cl.Plotly(figure=fig, name="可视化图表", display="inline").send()

                            if len(final_answer) > 10000:

                                # 如果内容太长，部分作为正文，全文作为附件
                                ui_msg.content = "查询结果较多，已为您生成详细报告（见下方附件）。\n\n" + final_answer[:500] + "..."
                                await ui_msg.update()
                                
                                # 发送全文附件
                                text_element = cl.Text(name="详细查询结果", content=final_answer, display="inline")
                                await cl.Message(content="点击展开完整结果：", elements=[text_element]).send()
                            else:
                                ui_msg.content = final_answer
                                await ui_msg.update()
                        else:
                            step.output = f"节点 {node_name} 执行完毕"

    except Exception as e:
        ui_msg.content = f"⚠️ 抱歉，查询发生错误：\n```python\n{str(e)}\n```"
        await ui_msg.update()
    finally:
        elapsed_ms = int((time.monotonic() - start_ts) * 1000)
        logger.info("Thread %s finished in %sms", thread_id, elapsed_ms)
