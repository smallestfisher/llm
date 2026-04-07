import asyncio
from core.graph import get_workflow
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("test_single")

async def test_single_table_logic():
    print("\n" + "="*50)
    print("🎯 开始 BOE Data Copilot 单表业务逻辑测试")
    print("="*50 + "\n")
    
    workflow = get_workflow()
    # 模拟单表模糊提问：PMC 关心 B11 工厂的在制瓶颈
    user_question = "分析一下 B11 工厂目前各个工序的 WIP 情况，有没有异常堆积？"
    print(f"👤 用户提问: {user_question}")
    
    config = {"configurable": {"thread_id": "single_table_test_001"}}
    inputs = {"question": user_question}
    
    try:
        async with AsyncSqliteSaver.from_conn_string("langgraph_memory.db") as saver:
            engine = workflow.compile(checkpointer=saver)
            
            async for output in engine.astream(inputs, config=config):
                for node_name, state in output.items():
                    if node_name == "normalize_question":
                        print(f"🔍 [归一化]: {state.get('normalized_question')}")
                    elif node_name == "get_schema":
                        # 验证是否只加载了 WIP 表
                        schema = state.get('table_schema', '')
                        is_single = "work_in_progress" in schema and "daily_inventory" not in schema
                        print(f"📚 [按需加载]: {'✅ 仅加载 WIP 表' if is_single else '⚠️ 全量加载'}")
                    elif node_name == "write_sql":
                        print(f"✍️ [生成 SQL]:\n{state.get('sql_query')}")
                    elif node_name == "execute_sql":
                        if state.get("sql_error"):
                            print(f"❌ [执行失败]: {state.get('sql_error')}")
                        else:
                            print(f"🚀 [执行成功]: 查出 {len(state.get('db_result', []))} 条工序数据")
                    elif node_name == "generate_answer":
                        print("\n🤖 [AI 最终回复]:")
                        print("-" * 30)
                        print(state.get('final_answer'))
                        print("-" * 30)

    except Exception as e:
        print(f"❌ 测试异常: {e}")

if __name__ == "__main__":
    asyncio.run(test_single_table_logic())
