from core.graph import create_backend_engine

def main():
    print("🚀 初始化 BOE Data Copilot 后端引擎...")
    engine = create_backend_engine()
    print("✅ 引擎启动成功！(输入 'quit' 退出)\n")
    
    while True:
        user_input = input("👤 请输入你的查询需求: ")
        if user_input.lower() in ['quit', 'exit', 'q']:
            break
            
        if not user_input.strip():
            continue
            
        print("\n⏳ 正在思考并执行工作流...")
        
        # 初始化图的输入状态
        inputs = {"question": user_input}
        
        # stream 方法可以在控制台打印出每一个节点的执行进度
        for output in engine.stream(inputs):
            for node_name, state in output.items():
                print(f"   ⚙️ 节点 [{node_name}] 执行完毕")
                
                # 你可以在这里打印中间过程进行 Debug
                if node_name == "write_sql":
                    print(f"      -> 生成的 SQL: {state['sql_query']}")
                elif node_name == "execute_sql":
                    if state.get('sql_error'):
                        print(f"      -> ❌ SQL 报错: {state['sql_error']}")
                    else:
                        print(f"      -> 📊 查出原始数据长度: {len(state['db_result'])} 字符")

        # 获取最终结果
        # state 此时保留了最后一个节点输出的 final_answer
        print("\n🤖 AI 助理回复:")
        print("================================")
        print(state.get("final_answer", "无结果"))
        print("================================\n")

if __name__ == "__main__":
    main()
