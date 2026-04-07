# 1. 顶部新增引入
import sqlite3
import json
import os
import logging
import re
try:
    import pandas as pd
except Exception:
    pd = None
from langgraph.checkpoint.sqlite import SqliteSaver

from typing import TypedDict, Annotated
import operator
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END

from core.database import get_db_connection
from core.prompts import TEXT2SQL_PROMPT, ANSWER_PROMPT, build_intent_prompt
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
    # 🔴 核心：Annotated + operator.add 表示每次返回历史记录时，自动往列表里追加，而不是覆盖
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

# ==========================================
# 2. 定义节点 (Nodes)
# ==========================================
def node_get_schema(state: GraphState):
    schema = db.get_table_info()
    if DEBUG_TRACE:
        logger.info("table_schema_preview=%s", (schema[:1200] + "...") if len(schema) > 1200 else schema)
    return {"table_schema": schema}


def _extract_headers(sql: str):
    m = re.search(r"select\\s+(.*?)\\s+from\\s", sql, re.IGNORECASE | re.DOTALL)
    if not m:
        return []
    parts = [p.strip() for p in m.group(1).split(",")]
    headers = []
    for p in parts:
        alias = re.search(r"\\bas\\s+([\\w_]+)\\b", p, re.IGNORECASE)
        if alias:
            headers.append(alias.group(1))
        else:
            headers.append(p.split(".")[-1].strip("` "))
    return headers


def _strip_limit(sql: str) -> str:
    return re.sub(r"\\s+limit\\s+\\d+(\\s*,\\s*\\d+)?\\s*$", "", sql, flags=re.IGNORECASE).strip()

def node_normalize_question(state: GraphState):
    normalized, hits = normalize_question(state["question"])
    if DEBUG_TRACE:
        logger.info("normalized_question=%s hits=%s", normalized, hits)
    return {"normalized_question": normalized, "lexicon_hits": hits}

def node_write_sql(state: GraphState):
    # 🔴 巧妙的技巧：把记忆拼在当前问题前面传给 LLM，这样你就不需要修改 prompt 文件了！
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
        return {"sql_query": "", "sql_error": "仅允许只读 SELECT 查询。"}
    # 明细查询默认加 LIMIT；汇总/聚合不强制 LIMIT
    is_aggregate = (" group by " in lower) or any(k in lower for k in ("count(", "sum(", "avg(", "min(", "max("))
    if (not is_aggregate) and " limit " not in lower and not lower.endswith("limit") and not lower.endswith("limit "):
        sql = f"{sql} LIMIT 200"

    return {"sql_query": sql}

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
        return {"db_result": "", "sql_error": str(e)}

def node_generate_answer(state: GraphState):
    if state.get("sql_error"):
        answer = f"⚠️ 数据库查询出错：\n{state['sql_error']}"
        # 出错也要记入脑子
        return {
            "final_answer": answer,
            "chat_history": [f"问: {state['question']}\n答: {answer}"]
        }

    db_result = state.get("db_result")
    sql_query = state.get("sql_query", "")
    lower_sql = sql_query.lower()

    # Deterministic formatting for any structured result to avoid LLM hallucination
    if isinstance(db_result, list) and db_result:
        is_tuple_rows = all(isinstance(r, tuple) for r in db_result)
        if is_tuple_rows:
            headers = state.get("columns") or _extract_headers(sql_query)
            if not headers or len(headers) != len(db_result[0]):
                headers = [f"col{i+1}" for i in range(len(db_result[0]))]
            if pd is not None:
                df = pd.DataFrame(db_result, columns=headers)
                table = df.to_markdown(index=False)
            else:
                lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
                for row in db_result:
                    lines.append("| " + " | ".join([str(v) for v in row]) + " |")
                table = "\\n".join(lines)
            # Add time range note if available
            time_note = ""
            filters = state.get("refined_filters") or {}
            if filters.get("recent_days"):
                days = filters["recent_days"]
                time_note = f"时间范围：最近 {days} 天（CURDATE()-INTERVAL {days} DAY 至 CURDATE()）\\n\\n"
            elif filters.get("date_from") or filters.get("date_to"):
                df = filters.get("date_from") or ""
                dt = filters.get("date_to") or ""
                time_note = f"时间范围：{df} 至 {dt}\\n\\n"
            elif filters.get("month") or filters.get("month_from") or filters.get("month_to"):
                m = filters.get("month") or ""
                mf = filters.get("month_from") or ""
                mt = filters.get("month_to") or ""
                if m:
                    time_note = f"时间范围：{m}\\n\\n"
                else:
                    time_note = f"时间范围：{mf} 至 {mt}\\n\\n"
            elif filters.get("latest") is True:
                time_note = "时间范围：最新一期（按系统时间/回退到最大值）\\n\\n"

            count_note = ""
            if state.get("row_count") is not None:
                count_note = f"总行数：{state.get('row_count')}\\n\\n"
            if state.get("truncated") is True:
                count_note += f"结果过多，已仅展示前 {SAMPLE_LIMIT} 行样例。\\n\\n"

            answer = "查询结果如下：\\n\\n" + time_note + count_note + table
            return {
                "final_answer": answer,
                "chat_history": [f"问: {state['question']}\\n答: {answer}"]
            }

    prompt = PromptTemplate.from_template(ANSWER_PROMPT)
    chain = prompt | llm

    response = chain.invoke({
        "question": state["question"],
        "sql_query": sql_query,
        "db_result": db_result
    })

    answer = response.content
    
    # 🔴 核心：正常回答完毕后，把这轮对话返回。因为定义了 operator.add，它会自动追加到记忆列表里
    return {
        "final_answer": answer,
        "chat_history": [f"问: {state['question']}\n答: {answer}"]
    }

# ==========================================
# 3. 编排工作流 (Compile Graph)
# ==========================================
def create_backend_engine():
    workflow = StateGraph(GraphState)

    workflow.add_node("get_schema", node_get_schema)
    workflow.add_node("normalize_question", node_normalize_question)
    workflow.add_node("extract_intent", node_extract_intent)
    workflow.add_node("refine_filters", node_refine_filters)
    workflow.add_node("write_sql", node_write_sql)
    workflow.add_node("execute_sql", node_execute_sql)
    workflow.add_node("generate_answer", node_generate_answer)

    workflow.set_entry_point("get_schema")
    workflow.add_edge("get_schema", "normalize_question")
    workflow.add_edge("normalize_question", "extract_intent")
    workflow.add_edge("extract_intent", "refine_filters")
    workflow.add_edge("refine_filters", "write_sql")
    workflow.add_edge("write_sql", "execute_sql")
    workflow.add_edge("execute_sql", "generate_answer")
    workflow.add_edge("generate_answer", END)


     # 🔴 核心变化：将记忆存入当前目录的 langgraph_memory.db
    conn = sqlite3.connect("langgraph_memory.db", check_same_thread=False)
    memory = SqliteSaver(conn)

    return workflow.compile(checkpointer=memory)
