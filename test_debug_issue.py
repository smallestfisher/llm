import asyncio
from core.graph import get_workflow
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_debug")

async def test_debug_query():
    workflow = get_workflow()
    user_question = "当前处于array阶段的有哪些"
    print(f"\n👤 测试问题: {user_question}")
    
    config = {"configurable": {"thread_id": "debug_thread_002"}}
    inputs = {"question": user_question}
    
    try:
        async with AsyncSqliteSaver.from_conn_string("langgraph_memory.db") as saver:
            engine = workflow.compile(checkpointer=saver)
            async for output in engine.astream(inputs, config=config):
                for node_name, state in output.items():
                    print(f"--- Node: {node_name} ---")
                    if "sql_query" in state:
                        print(f"SQL: {state['sql_query']}")
                    if "sql_error" in state and state["sql_error"]:
                        print(f"Error: {state['sql_error']}")
                    if "db_result" in state:
                        print(f"Result Type: {type(state['db_result'])}")
                    if "final_answer" in state:
                        print(f"Final Answer: {state['final_answer'][:200]}...")

    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_debug_query())
