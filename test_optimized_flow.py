from core.graph import create_backend_engine

def test_flow():
    print("🚀 Initializing engine...")
    engine = create_backend_engine()
    
    inputs = {"question": "查询 daily_inventory 表中最新的库存量"}
    print(f"Testing with question: {inputs['question']}")
    
    # We use a config for recursion_limit if needed, but default is 25
    config = {"configurable": {"thread_id": "test_thread"}}
    
    for output in engine.stream(inputs, config=config):
        for node_name, state in output.items():
            print(f"   Node [{node_name}] finished")
            if "table_schema" in state:
                 print(f"      Schema loaded: {len(state['table_schema'])} chars")
            if "intent" in state:
                 print(f"      Intent: {state['intent']}")
            if "sql_query" in state:
                 print(f"      SQL: {state['sql_query']}")

    # Final state check
    final_state = engine.get_state(config).values
    print("\nFinal Answer Preview:")
    print(final_state.get("final_answer")[:100] if final_state.get("final_answer") else "No answer")

if __name__ == "__main__":
    try:
        test_flow()
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
