from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Any

try:
    import pandas as pd
except Exception:
    pd = None

from app.execution.llm_client import llm_complete


MAX_TABLE_ROWS = int(os.getenv("MAX_TABLE_ROWS", "200"))


def build_answer_payload(
    *,
    question: str,
    sql_query: str,
    sql_error: str,
    db_result: list[Any],
    columns: list[str],
    row_count: int | None,
    truncated: bool,
    answer_prompt: str,
) -> dict[str, Any]:
    if sql_error:
        answer = f"[warning] 数据库查询出错:\n{sql_error}"
        return {
            "final_answer": answer,
            "chart_data": None,
            "table_data": [],
            "table_columns": columns,
            "row_count": row_count,
            "truncated": truncated,
            "chat_history": [f"问: {question}\n答: {answer}"],
        }

    if pd is None:
        db_preview = json.dumps(db_result[:20], ensure_ascii=False)
        table_data = db_result[:MAX_TABLE_ROWS]
        summary_text = f"查询结果共 {row_count or len(db_result)} 条记录。" if db_result else "未查询到数据。"
        is_aggregate = any(token in sql_query.lower() for token in (" group by ", "count(", "sum(", "avg(", "min(", "max("))
    else:
        if db_result and columns:
            df = pd.DataFrame(db_result, columns=columns)
        elif db_result:
            df = pd.DataFrame(db_result)
        else:
            df = pd.DataFrame()

        lower_sql = sql_query.lower()
        is_aggregate = (" group by " in lower_sql) or any(token in lower_sql for token in ("count(", "sum(", "avg(", "min(", "max("))
        if not df.empty:
            total_count = row_count or len(df)
            summary_text = f"查询结果共 {total_count} 条记录。"
            numeric_cols = df.select_dtypes(include=["number"]).columns
            if len(numeric_cols) > 0:
                summary_text += f" 关键指标汇总: {df[numeric_cols].sum().to_dict()}"
            db_preview = df.head(20).to_json(orient="records", force_ascii=False)
            for column in df.select_dtypes(include=["object"]).columns:
                if any(isinstance(value, Decimal) for value in df[column]):
                    df[column] = df[column].astype(float)
            table_data = df.head(MAX_TABLE_ROWS).to_dict(orient="records")
        else:
            db_preview = "[]"
            table_data = []
            summary_text = "未查询到数据。"

    if db_result and not is_aggregate:
        if truncated and row_count:
            answer = f"已查询到 {row_count} 条记录，当前展示前 {len(db_result)} 条。结果集较大，请结合筛选条件缩小范围后继续查看。"
        else:
            answer = f"已查询到 {row_count or len(db_result)} 条记录，请查看下方结果表。"
        return {
            "final_answer": answer,
            "chart_data": None,
            "table_data": table_data,
            "table_columns": columns,
            "row_count": row_count,
            "truncated": truncated,
            "chat_history": [f"问: {question}\n答: {answer}"],
        }

    answer = llm_complete(answer_prompt.format(question=question, sql_query=sql_query, db_result=db_preview, data_summary=summary_text))
    return {
        "final_answer": answer,
        "chart_data": None,
        "table_data": table_data,
        "table_columns": columns,
        "row_count": row_count,
        "truncated": truncated,
        "chat_history": [f"问: {question}\n答: {answer}"],
    }
