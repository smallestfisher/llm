import asyncio
from core.graph import get_workflow
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import logging

# 配置日志输出到控制台
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("test_e2e")

async def test_complex_query():
    print("\n" + "="*50)
    print("🚀 开始 BOE Data Copilot E2E 业务逻辑测试")
    print("="*50 + "\n")
    
    workflow = get_workflow()
    # 模拟用户问题：涉及 production_actuals 和 monthly_plan_approved 的跨表关联
    user_question = "查询本月各产品的生产达成率（实际产出 / 计划目标）"
    print(f"👤 用户提问: {user_question}")
    
    config = {"configurable": {"thread_id": "e2e_test_thread_001"}}
    inputs = {"question": user_question}
    
    try:
        async with AsyncSqliteSaver.from_conn_string("langgraph_memory.db") as saver:
            engine = workflow.compile(checkpointer=saver)
            
            async for output in engine.astream(inputs, config=config):
                for node_name, state in output.items():
                    print(f"\n✅ 节点 [{node_name}] 执行完毕:")
                    
                    if node_name == "extract_intent":
                        print(f"   🎯 识别意图: {state.get('intent')}")
                    elif node_name == "get_schema":
                        print(f"   📚 加载表: {state.get('table_schema')[:200]}...")
                    elif node_name == "write_sql":
                        print(f"   ✍️ 生成 SQL:\n{state.get('sql_query')}")
                    elif node_name == "execute_sql":
                        if state.get("sql_error"):
                            print(f"   ❌ SQL 报错: {state.get('sql_error')}")
                        else:
                            print(f"   🚀 查询成功，返回数据长度: {len(str(state.get('db_result')))}")
                    elif node_name == "reflect_sql":
                        print(f"   🔧 正在进行纠错反思，重试次数: {state.get('retry_count')}")
                    elif node_name == "generate_answer":
                        print("\n🤖 AI 最终回复预览:")
                        print("-" * 30)
                        # 只打印前300字符，防止表格刷屏
                        ans = state.get('final_answer', '')
                        print(ans[:500] + ("..." if len(ans) > 500 else ""))
                        print("-" * 30)

    except Exception as e:
        print(f"❌ 测试发生异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_complex_query())
