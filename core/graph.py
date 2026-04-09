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
from openai import OpenAI
from langgraph.graph import StateGraph, END

from core.database import get_db_connection
from core.prompts import build_text2sql_prompt, build_answer_prompt, build_reflect_sql_prompt, build_guard_prompt, build_query_parse_prompt
from core.lexicon import normalize_question
from core.heuristics import refine_simple_filters, extract_recent_days, has_explicit_date, guess_single_table
from core.config.loader import load_intents, load_tables, load_prompt_context

from datetime import date, datetime
from decimal import Decimal



logger = logging.getLogger("boe.graph")
DEBUG_TRACE = os.getenv("DEBUG_TRACE", "0") == "1"

LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen3-14B")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-no-key")

_openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
db = get_db_connection()

MAX_DETAIL_ROWS = int(os.getenv("MAX_DETAIL_ROWS", "2000"))
SAMPLE_LIMIT = int(os.getenv("SAMPLE_LIMIT", "5000"))
MAX_TABLE_ROWS = int(os.getenv("MAX_TABLE_ROWS", "200"))
AUTO_TRUNCATE_ROWS = int(os.getenv("AUTO_TRUNCATE_ROWS", "50000"))


def _llm_complete(prompt: str, stream: bool = False) -> str:
    """流式 LLM 调用"""
    resp = _openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=LLM_TEMPERATURE,
        stream=stream,
    )
    if not stream:
        return (resp.choices[0].message.content or "").strip()
    
    full_text = ""
    reasoning_started = False
    content_started = False

    def _extract_stream_text(delta, attr_name: str) -> str:
        value = getattr(delta, attr_name, None)
        if not value:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts = []
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("content") or ""))
                else:
                    parts.append(str(getattr(item, "text", "") or getattr(item, "content", "") or ""))
            return "".join(parts)
        if isinstance(value, dict):
            return str(value.get("text") or value.get("content") or "")
        return str(getattr(value, "text", "") or getattr(value, "content", "") or "")

    for chunk in resp:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue
        delta = getattr(choices[0], "delta", None)
        if not delta:
            continue

        reasoning_text = ""
        for field_name in ("reasoning_content", "reasoning", "reasoning_text"):
            reasoning_text = _extract_stream_text(delta, field_name)
            if reasoning_text:
                break

        if DEBUG_TRACE and reasoning_text:
            if not reasoning_started:
                print("\n[REASONING]: ", end="", flush=True)
                reasoning_started = True
            print(reasoning_text, end="", flush=True)

        content_text = _extract_stream_text(delta, "content")
        if content_text:
            if DEBUG_TRACE and reasoning_started and not content_started:
                print("\n[CONTENT]: ", end="", flush=True)
            elif not DEBUG_TRACE and not content_started:
                print("\n[STREAMING]: ", end="", flush=True)
            content_started = True
            print(content_text, end="", flush=True)
            full_text += content_text

    if DEBUG_TRACE and reasoning_started:
        print("", flush=True)
    if content_started:
        print("\n", flush=True)
    return full_text.strip()

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
    table_data: list
    table_columns: list
    row_count: int
    truncated: bool

# ==========================================
# 2. 定义节点 (Nodes) - 注入思维链流式输出
# ==========================================
def node_get_schema(state: GraphState):
    print("\n>>> [思维链] 正在动态加载相关表 Schema...")
    refined = state.get("refined_filters") or {}
    target_table = refined.get("table")
    
    # 策略 1: 如果意图识别直接给出了表名，优先加载该表
    def _format_schema(table_names=None):
        tables = load_tables()
        if table_names:
            tables = {k: v for k, v in tables.items() if k in table_names}
        lines = []
        for name, info in tables.items():
            desc = info.get("description", "")
            cols = info.get("columns", [])
            lines.append(f"Table: {name}")
            if desc:
                lines.append(f"Description: {desc}")
            if cols:
                lines.append("Columns: " + ", ".join(cols))
            lines.append("")
        return "\n".join(lines).strip()

    if target_table:
        schema = _format_schema([target_table])
    else:
        norm_q = (state.get("normalized_question") or state["question"]).lower()
        all_tables = list(load_tables().keys())
        hit_tables = [t for t in all_tables if t in norm_q]
        schema = _format_schema(hit_tables) if hit_tables else _format_schema()
    return {"table_schema": schema}

def node_parse_query(state: GraphState):
    print("\n>>> [思维链] 正在解析问题语义与查询意图...")
    rule_normalized, hits = normalize_question(state["question"])
    prompt_text = build_query_parse_prompt(load_intents(), list(load_tables().keys()))
    prompt = prompt_text.format(
        question=state["question"],
        rule_normalized_question=rule_normalized,
    )
    data = _safe_json_loads(_llm_complete(prompt))
    normalized_question = (data.get("normalized_question") or rule_normalized or state["question"]).strip()
    intent = (data.get("intent") or "unknown").strip()
    confidence = float(data.get("confidence") or 0.0)
    filters = data.get("filters") or {}
    return {
        "normalized_question": normalized_question,
        "lexicon_hits": hits,
        "intent": intent,
        "intent_confidence": confidence,
        "intent_filters": filters,
    }

def node_write_sql(state: GraphState):
    print("\n>>> [思维链] 正在编写 SQL (包含业务逻辑注入)...")
    retry_count = state.get("retry_count") or 0
    history_list = state.get("chat_history", [])
    history_text = "\n".join(history_list) if history_list else ""
    enhanced_question = f"【前情提要】\n{history_text}\n\n【当前用户问题】\n{state.get('normalized_question') or state['question']}"
    
    prompt = build_text2sql_prompt(
        table_schema=state["table_schema"],
        question=enhanced_question,
        prompt_context=load_prompt_context(),
    )
    sql = _llm_complete(prompt, stream=True)
    if sql.startswith("```sql"): sql = sql[6:]
    if sql.startswith("```"): sql = sql[3:]
    if sql.endswith("```"): sql = sql[:-3]
    sql = sql.strip()
    if ";" in sql:
        sql = sql.split(";", 1)[0].strip()
    return {"sql_query": sql, "retry_count": retry_count}

def node_reflect_sql(state: GraphState):
    print("\n>>> [思维链] SQL 报错，正在反思错误原因并尝试修复...")
    retry_count = (state.get("retry_count") or 0) + 1
    prompt = build_reflect_sql_prompt(
        question=state["question"],
        table_schema=state["table_schema"],
        sql_query=state["sql_query"],
        error_message=state["sql_error"],
        prompt_context=load_prompt_context(),
    )
    sql = _llm_complete(prompt, stream=True)
    if sql.startswith("```sql"): sql = sql[6:]
    if sql.startswith("```"): sql = sql[3:]
    if sql.endswith("```"): sql = sql[:-3]
    return {"sql_query": sql.strip(), "retry_count": retry_count, "sql_error": ""}


def _strip_limit(sql: str) -> str:
    return re.sub(r"\s+limit\s+\d+(\s*,\s*\d+)?\s*$", "", sql, flags=re.IGNORECASE).strip()

def node_refine_filters(state: GraphState):
    intent = state.get("intent")
    filters = state.get("intent_filters") or {}
    question = state.get("normalized_question") or state["question"]
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
    print("\n>>> [思维链] 正在执行 SQL...")
    sql = state["sql_query"]
    if not sql:
        return {"db_result": "", "sql_error": state.get("sql_error") or "SQL 为空"}
    try:
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
                if count_res and isinstance(count_res[0], (list, tuple)):
                    row_count = int(count_res[0][0])
            except Exception:
                row_count = None
            if row_count is not None and row_count > AUTO_TRUNCATE_ROWS and " limit " not in lower_sql:
                sql = f"{sql} LIMIT {SAMPLE_LIMIT}"
                truncated = True
        
        # 执行查询
        result, columns = db.run(sql)
        logger.info(f"========================={columns}")   
        # 确保 result 是列表格式，元素是 list
        formatted_result = []
        for r in result:
            new_elements = []
            for item in r:
                # 检测是否为日期/时间对象
                if isinstance(item, (date, datetime)):
                    new_elements.append(item.strftime("%Y-%m-%d"))
                else:
                    new_elements.append(item)
            formatted_result.append(new_elements)
        
        return {
            "db_result": formatted_result,
            "sql_error": "",
            "row_count": row_count,
            "truncated": truncated,
            "table_columns": columns,
        }
    except Exception as e:
        logger.error(f"SQL Execution Error: {e}")
        return {"db_result": [], "sql_error": str(e)}


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

def node_check_guard(state: GraphState):
    print("\n>>> [思维链] 正在进行安全合规检查...")
    prompt = build_guard_prompt(question=state["question"], prompt_context=load_prompt_context())
    decision = _llm_complete(prompt)
    if "REJECT" in decision:
        return {"intent": "REJECT"}
    return {"intent": state["intent"]}

def node_generate_answer(state: GraphState):
    print("\n>>> [思维链] 正在生成专业回答...")
    if state.get("intent") == "REJECT":
        answer = "抱歉，作为 BOE 生产辅助驾驶系统，我仅支持处理生产制造相关的业务数据查询。请问有什么业务需求需要我协助吗？"
        return {
            "final_answer": answer,
            "chat_history": [f"问: {state['question']}\n答: {answer}"]
        }
    if state.get("sql_error"):
        answer = f"⚠️ 数据库查询出错：\n{state['sql_error']}"
        return {
            "final_answer": answer,
            "chat_history": [f"问: {state['question']}\n答: {answer}"]
        }

    db_result = state.get("db_result", [])
    sql_query = state.get("sql_query", "")
    columns = state.get("table_columns", [])
    row_count = state.get("row_count")
    truncated = bool(state.get("truncated"))
    lower_sql = sql_query.lower()
    is_aggregate = (" group by " in lower_sql) or any(k in lower_sql for k in ("count(", "sum(", "avg(", "min(", "max("))

    # 使用 pandas 构建 DataFrame
    if db_result and columns:
        df = pd.DataFrame(db_result, columns=columns)
    elif db_result:
        df = pd.DataFrame(db_result)
    else:
        df = pd.DataFrame()

    summary_text = ""
    chart_json = None
    
    if not df.empty:
        total_count = row_count or len(df)
        summary_text = f"查询结果共 {total_count} 条记录。"
        # 补充数值列统计
        numeric_cols = df.select_dtypes(include=['number']).columns
        if not numeric_cols.empty:
            summary_text += f" 关键指标汇总: {df[numeric_cols].sum().to_dict()}"

        # 预览数据（限制前 20 行给 LLM）
        db_preview = df.head(20).to_json(orient="records", force_ascii=False)
        # table_data = df.to_dict(orient="records")
       

        # 2. 将包含 Decimal 类型的列转换为 float
        for col in df.select_dtypes(include=['object']).columns:
            if any(isinstance(val, Decimal) for val in df[col]):
                df[col] = df[col].astype(float)

        # 3. 【最关键的修改】：把 DataFrame 转换回原生字典列表！
        # 这样赋值给 table_data，LangGraph 的 msgpack 序列化就不会再报错了
        # table_data = df.to_dict(orient="records")
        table_data = df.to_markdown(index=False, floatfmt=",.2f")

        logger.info(f"table_data 样例: {table_data[:2]}") # 打印前两行看看
    else:
        db_preview = "[]"
        table_data = []
        summary_text = "未查询到数据。"

    if not df.empty and not is_aggregate:
        if truncated and row_count:
            answer = f"已查询到 {row_count} 条记录，当前展示前 {len(df)} 条。结果集较大，请结合筛选条件缩小范围后继续查看。"
        else:
            answer = f"已查询到 {row_count or len(df)} 条记录，请查看下方结果表。"
        return {
            "final_answer": answer,
            "chart_data": chart_json,
            "table_data": table_data,
            "table_columns": columns,
            "chat_history": [f"问: {state['question']}\n答: {answer}"],
            "row_count": row_count,
            "truncated": truncated,
        }

    prompt = build_answer_prompt(
        question=state["question"],
        sql_query=sql_query,
        db_result=db_preview,
        data_summary=summary_text,
        prompt_context=load_prompt_context(),
    )

    logger.info(f"prompt: {prompt}")

    answer = _llm_complete(prompt)

    return {
        "final_answer": answer,
        "chart_data": chart_json,
        "table_data": table_data,
        "table_columns": columns,
        "chat_history": [f"问: {state['question']}\n答: {answer}"],
        "row_count": row_count,
        "truncated": truncated,
    }


def get_workflow():
    workflow = StateGraph(GraphState)
    workflow.add_node("parse_query", node_parse_query)
    workflow.add_node("check_guard", node_check_guard)
    workflow.add_node("refine_filters", node_refine_filters)
    workflow.add_node("get_schema", node_get_schema)
    workflow.add_node("write_sql", node_write_sql)
    workflow.add_node("execute_sql", node_execute_sql)
    workflow.add_node("reflect_sql", node_reflect_sql)
    workflow.add_node("generate_answer", node_generate_answer)
    workflow.set_entry_point("parse_query")
    workflow.add_edge("parse_query", "check_guard")

    def route_after_guard(state: GraphState):
        if state.get("intent") == "REJECT":
            return "generate_answer"
        return "refine_filters"

    workflow.add_conditional_edges("check_guard", route_after_guard, {
        "generate_answer": "generate_answer",
        "refine_filters": "refine_filters"
    })

    workflow.add_edge("refine_filters", "get_schema")
    workflow.add_edge("get_schema", "write_sql")
    workflow.add_edge("write_sql", "execute_sql")
    def route_after_execute(state: GraphState):
        if state.get("sql_error") and (state.get("retry_count") or 0) < 3:
            return "reflect_sql"
        return "generate_answer"
    workflow.add_conditional_edges("execute_sql", route_after_execute, {"reflect_sql": "reflect_sql", "generate_answer": "generate_answer"})
    workflow.add_edge("reflect_sql", "execute_sql")
    workflow.add_edge("generate_answer", END)
    return workflow


async def get_compiled_workflow():
    return get_workflow().compile()
