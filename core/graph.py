import sqlite3
import json
import os
import logging
import re
try:
    import pandas as pd
except Exception:
    pd = None
import plotly.express as px
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from typing import TypedDict, Annotated
import operator
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END

from core.database import get_db_connection
from core.prompts import TEXT2SQL_PROMPT, ANSWER_PROMPT, REFLECT_SQL_PROMPT, build_intent_prompt
from core.lexicon import normalize_question
from core.heuristics import refine_simple_filters, extract_recent_days, has_explicit_date, guess_single_table
from core.config.loader import load_intents, load_tables

logger = logging.getLogger("boe.graph")
DEBUG_TRACE = os.getenv("DEBUG_TRACE", "0") == "1"

llm = ChatOpenAI(model="Qwen/Qwen3-14B", temperature=0)
db = get_db_connection()

MAX_DETAIL_ROWS = int(os.getenv("MAX_DETAIL_ROWS", "2000"))
SAMPLE_LIMIT = int(os.getenv("SAMPLE_LIMIT", "200"))

# ==========================================
# 1. 定义状态总线 (加入 chat_history)
# ==========================================
class GraphState(TypedDict):
    question: str
    chat_history: Annotated[list, operator.add] 
    table_schema: str
    normalized_question: str
    lexicon_hits: list
    intent: str
    intent_confidence: float
    intent_filters: dict
    refined_filters: dict
    sql_query: str
    sql_error: str
    db_result: str
    final_answer: str
    retry_count: int
    chart_data: dict # 🔴 存放可视化图表 JSON

# ==========================================
# 2. 定义节点 (Nodes)
# ==========================================
def node_get_schema(state: GraphState):
    refined = state.get("refined_filters") or {}
    target_table = refined.get("table")
    
    # 策略 1: 如果意图识别直接给出了表名，优先加载该表
    if target_table:
        logger.info(f"Loading schema for specific table: {target_table}")
        schema = db.get_table_info(table_names=[target_table])
    else:
        # 策略 2: 扫描问题，看看是否提到了表名关键字
        norm_q = (state.get("normalized_question") or state["question"]).lower()
        all_tables = list(load_tables().keys())
        hit_tables = [t for t in all_tables if t in norm_q]
        
        if hit_tables:
            logger.info(f"Loading schema for matched tables: {hit_tables}")
            schema = db.get_table_info(table_names=hit_tables)
        else:
            # 策略 3: 兜底全量加载
            logger.info("No specific table identified, loading all target tables.")
            schema = db.get_table_info()

    if DEBUG_TRACE:
        logger.info("table_schema_preview=%s", (schema[:1200] + "...") if len(schema) > 1200 else schema)
    return {"table_schema": schema}


def _extract_headers(sql: str):
    m = re.search(r"select\s+(.*?)\s+from\s", sql, re.IGNORECASE | re.DOTALL)
    if not m:
        return []
    parts = [p.strip() for p in m.group(1).split(",")]
    headers = []
    for p in parts:
        alias = re.search(r"\bas\s+([\w_]+)\b", p, re.IGNORECASE)
        if alias:
            headers.append(alias.group(1))
        else:
            headers.append(p.split(".")[-1].strip("` "))
    return headers


def _strip_limit(sql: str) -> str:
    return re.sub(r"\s+limit\s+\d+(\s*,\s*\d+)?\s*$", "", sql, flags=re.IGNORECASE).strip()

def node_normalize_question(state: GraphState):
    logger.info("--- [思维链] 正在进行问题归一化，处理业务黑话 ---")
    normalized, hits = normalize_question(state["question"])
    if DEBUG_TRACE:
        logger.info("normalized_question=%s hits=%s", normalized, hits)
    return {"normalized_question": normalized, "lexicon_hits": hits}

def node_write_sql(state: GraphState):
    logger.info("--- [思维链] 正在根据表结构和业务逻辑编写 SQL ---")
    # 初始化/获取重试次数
    retry_count = state.get("retry_count") or 0
    
    # 🔴 巧妙的技巧：把记忆拼在当前问题前面传给 LLM
    history_list = state.get("chat_history", [])
    if history_list:
        history_text = "\n".join(history_list)
        # 如果有记忆，就把上下文拼在一起
        enhanced_question = f"【前情提要】\n{history_text}\n\n【当前用户问题】\n{state.get('normalized_question') or state['question']}"
    else:
        enhanced_question = state.get("normalized_question") or state["question"]

    prompt = PromptTemplate.from_template(TEXT2SQL_PROMPT)
    chain = prompt | llm

    response = chain.invoke({
        "table_schema": state["table_schema"],
        "question": enhanced_question # 传入带记忆的问题
    })

    sql = response.content.strip()
    if sql.startswith("```sql"): sql = sql[6:]
    if sql.startswith("```"): sql = sql[3:]
    if sql.endswith("```"): sql = sql[:-3]
    sql = sql.strip()
    # 只取第一条语句，避免多语句执行
    if ";" in sql:
        sql = sql.split(";", 1)[0].strip()
    # 仅允许 SELECT/CTE 查询
    lower = sql.lower()
    if not (lower.startswith("select") or lower.startswith("with")):
        return {"sql_query": "", "sql_error": "仅允许只读 SELECT 查询。", "retry_count": retry_count}
    
    # 不再在此强制加 LIMIT 200，交给 execute_sql 节点的动态截断逻辑处理
    return {"sql_query": sql, "retry_count": retry_count}

def node_reflect_sql(state: GraphState):
    """SQL 纠错节点"""
    logger.info("--- [思维链] 发现 SQL 报错，正在反思原因并尝试修复 ---")
    retry_count = (state.get("retry_count") or 0) + 1
    logger.warning(f"Reflecting on SQL error (Retry #{retry_count}): {state['sql_error']}")
    
    prompt = PromptTemplate.from_template(REFLECT_SQL_PROMPT)
    chain = prompt | llm

    response = chain.invoke({
        "question": state["question"],
        "table_schema": state["table_schema"],
        "sql_query": state["sql_query"],
        "error_message": state["sql_error"]
    })

    sql = response.content.strip()
    if sql.startswith("```sql"): sql = sql[6:]
    if sql.startswith("```"): sql = sql[3:]
    if sql.endswith("```"): sql = sql[:-3]
    
    return {"sql_query": sql.strip(), "retry_count": retry_count, "sql_error": ""}

def _safe_json_loads(text: str) -> dict:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except Exception:
                return {}
        return {}

def node_extract_intent(state: GraphState):
    prompt_text = build_intent_prompt(load_intents(), list(load_tables().keys()))
    prompt = PromptTemplate.from_template(prompt_text)
    chain = prompt | llm
    response = chain.invoke({"question": state.get("normalized_question") or state["question"]})
    data = _safe_json_loads(response.content)
    intent = (data.get("intent") or "unknown").strip()
    confidence = float(data.get("confidence") or 0.0)
    filters = data.get("filters") or {}
    return {
        "intent": intent,
        "intent_confidence": confidence,
        "intent_filters": filters,
    }

def node_refine_filters(state: GraphState):
    intent = state.get("intent")
    filters = state.get("intent_filters") or {}
    question = state.get("normalized_question") or state["question"]

    # If user says "最近N天" and didn't specify explicit dates, override model dates.
    recent_days = extract_recent_days(question)
    if recent_days and not has_explicit_date(question):
        filters = dict(filters)
        filters.pop("date_from", None)
        filters.pop("date_to", None)
        filters["recent_days"] = recent_days

    single_table = guess_single_table(question)
    if single_table:
        filters = dict(filters)
        filters["table"] = single_table

    if intent == "simple_table_query" or single_table:
        refined = refine_simple_filters(question, filters)
        return {"refined_filters": refined, "intent": "simple_table_query"}
    return {"refined_filters": filters}

def node_execute_sql(state: GraphState):
    logger.info("--- [思维链] 正在数据库执行生成的 SQL ---")
    sql = state["sql_query"]
    if not sql:
        return {"db_result": "", "sql_error": state.get("sql_error") or "SQL 为空"}
    try:
        logger.info("final_sql=%s", sql)
        lower_sql = sql.lower()
        is_select = lower_sql.strip().startswith("select") or lower_sql.strip().startswith("with")
        is_aggregate = (" group by " in lower_sql) or any(k in lower_sql for k in ("count(", "sum(", "avg(", "min(", "max("))

        row_count = None
        truncated = False
        if is_select and not is_aggregate:
            base_sql = _strip_limit(sql)
            count_sql = f"SELECT COUNT(*) FROM ({base_sql}) AS subq"
            try:
                count_res = db.run(count_sql)
                if isinstance(count_res, list) and count_res and isinstance(count_res[0], tuple):
                    row_count = int(count_res[0][0])
            except Exception:
                row_count = None

            if row_count is not None and row_count > MAX_DETAIL_ROWS and " limit " not in lower_sql:
                sql = f"{sql} LIMIT {SAMPLE_LIMIT}"
                truncated = True

        result = db.run(sql)
        result_len = len(result) if isinstance(result, str) else None
        columns = _extract_headers(sql)
        return {
            "db_result": result,
            "sql_error": "",
            "db_result_len": result_len,
            "row_count": row_count,
            "truncated": truncated,
            "columns": columns,
        }
    except Exception as e:
        logger.error(f"--- [思维链] SQL 执行报错: {str(e)} ---")
        return {"db_result": "", "sql_error": str(e)}

def node_generate_answer(state: GraphState):
    if state.get("sql_error"):
        answer = f"⚠️ 数据库查询出错：\n{state['sql_error']}"
        return {
            "final_answer": answer,
            "chat_history": [f"问: {state['question']}\n答: {answer}"]
        }

    db_result = state.get("db_result")
    sql_query = state.get("sql_query", "")
    
    # 使用 Pandas 自动化分析
    df = None
    summary_text = ""
    chart_json = None
    
    if isinstance(db_result, list) and db_result:
        headers = state.get("columns") or _extract_headers(sql_query)
        if headers and len(headers) == len(db_result[0]):
            df = pd.DataFrame(db_result, columns=headers)
            
            # --- 可视化决策引擎 ---
            try:
                # 如果有 GROUP BY 且有数值列，自动生成图表
                num_cols = df.select_dtypes(include=['number']).columns.tolist()
                cat_cols = df.select_dtypes(include=['object']).columns.tolist()
                
                if len(cat_cols) >= 1 and len(num_cols) >= 1 and len(df) > 1:
                    # 优先选第一个分类字段和第一个数值字段绘图
                    # 如果分类字段是日期，画折线图；否则画柱状图
                    x_col = cat_cols[0]
                    y_col = num_cols[0]
                    
                    if "date" in x_col.lower() or "month" in x_col.lower():
                        fig = px.line(df, x=x_col, y=y_col, title=f"{y_col} 变化趋势", markers=True)
                    else:
                        fig = px.bar(df, x=x_col, y=y_col, title=f"各 {x_col} 的 {y_col} 分布", color=x_col)
                    
                    chart_json = fig.to_json()
            except Exception as e:
                logger.warning(f"Failed to generate chart: {e}")

            # --- 智能统计摘要 ---
            if len(df) > 30:
                summary_parts = []
                summary_parts.append(f"数据总量: {len(df)} 条记录。")
                for col in df.columns:
                    if df[col].dtype == "object" or any(k in col.lower() for k in ["code", "name", "process"]):
                        v_counts = df[col].value_counts().head(5).to_dict()
                        if len(v_counts) > 1:
                            summary_parts.append(f"- {col} 分布: {v_counts}")
                    if any(k in col.lower() for k in ["qty", "amount", "rate", "yield"]):
                        summary_parts.append(f"- {col} 汇总: 总计={df[col].sum():.2f}, 平均={df[col].mean():.2f}")
                summary_text = "\n".join(summary_parts)

    # 给大模型看前 50 行预览
    db_preview = df.head(50).to_markdown(index=False) if df is not None else str(db_result)

    prompt = PromptTemplate.from_template(ANSWER_PROMPT)
    chain = prompt | llm

    response = chain.invoke({
        "question": state["question"],
        "sql_query": sql_query,
        "db_result": db_preview,
        "data_summary": summary_text
    })

    answer = response.content
    
    # 最终结果展示
    full_table = ""
    if df is not None and len(df) > 0:
        full_table = "\n\n" + df.to_markdown(index=False)
    
    final_output = answer + full_table

    return {
        "final_answer": final_output,
        "chart_data": chart_json, # 传给前端渲染
        "chat_history": [f"问: {state['question']}\n答: {answer}"]
    }

# ==========================================
# 3. 编排工作流 (Compile Graph)
# ==========================================
def get_workflow():
    workflow = StateGraph(GraphState)

    workflow.add_node("normalize_question", node_normalize_question)
    workflow.add_node("extract_intent", node_extract_intent)
    workflow.add_node("refine_filters", node_refine_filters)
    workflow.add_node("get_schema", node_get_schema)
    workflow.add_node("write_sql", node_write_sql)
    workflow.add_node("execute_sql", node_execute_sql)
    workflow.add_node("reflect_sql", node_reflect_sql)
    workflow.add_node("generate_answer", node_generate_answer)

    workflow.set_entry_point("normalize_question")
    workflow.add_edge("normalize_question", "extract_intent")
    workflow.add_edge("extract_intent", "refine_filters")
    workflow.add_edge("refine_filters", "get_schema")
    workflow.add_edge("get_schema", "write_sql")
    workflow.add_edge("write_sql", "execute_sql")

    # 🔴 核心：条件路由
    def route_after_execute(state: GraphState):
        if state.get("sql_error") and (state.get("retry_count") or 0) < 3:
            return "reflect_sql"
        return "generate_answer"

    workflow.add_conditional_edges(
        "execute_sql",
        route_after_execute,
        {
            "reflect_sql": "reflect_sql",
            "generate_answer": "generate_answer"
        }
    )

    workflow.add_edge("reflect_sql", "execute_sql") # 反思后重试执行
    workflow.add_edge("generate_answer", END)

    return workflow
