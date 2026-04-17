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


def _jsonable_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    return value


def _normalize_rows(db_result: list[Any]) -> list[Any]:
    normalized: list[Any] = []
    for row in db_result:
        if isinstance(row, dict):
            normalized.append({key: _jsonable_value(value) for key, value in row.items()})
        elif isinstance(row, (list, tuple)):
            normalized.append([_jsonable_value(value) for value in row])
        else:
            normalized.append(_jsonable_value(row))
    return normalized


def _build_evidence_json(columns: list[str], db_result: list[Any], *, limit: int = 10) -> str:
    if not db_result:
        return "[]"
    evidence_rows: list[dict[str, Any]] = []
    for index, row in enumerate(_normalize_rows(db_result[:limit]), start=1):
        if isinstance(row, dict):
            evidence_rows.append({"row_no": index, "values": row})
            continue
        if isinstance(row, (list, tuple)):
            mapped = {}
            for col_index, value in enumerate(row):
                key = columns[col_index] if col_index < len(columns) and columns[col_index] else f"col_{col_index + 1}"
                mapped[key] = value
            evidence_rows.append({"row_no": index, "values": mapped})
    return json.dumps(evidence_rows, ensure_ascii=False)


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
    normalized_result = _normalize_rows(db_result)

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
        db_preview = json.dumps(normalized_result[:20], ensure_ascii=False)
        table_data = normalized_result[:MAX_TABLE_ROWS]
        summary_text = f"查询结果共 {row_count or len(normalized_result)} 条记录。" if normalized_result else "未查询到数据。"
        is_aggregate = any(token in sql_query.lower() for token in (" group by ", "count(", "sum(", "avg(", "min(", "max("))
    else:
        if normalized_result and columns:
            df = pd.DataFrame(normalized_result, columns=columns)
        elif normalized_result:
            df = pd.DataFrame(normalized_result)
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

    if not normalized_result:
        answer = "未查到数据。请确认筛选条件（时间、工厂、产品、版本）后重试。"
        return {
            "final_answer": answer,
            "chart_data": None,
            "table_data": table_data,
            "table_columns": columns,
            "row_count": row_count or 0,
            "truncated": truncated,
            "chat_history": [f"问: {question}\n答: {answer}"],
        }

    if normalized_result and not is_aggregate:
        if truncated and row_count:
            answer = f"已查询到 {row_count} 条记录，当前展示前 {len(normalized_result)} 条。结果集较大，请结合筛选条件缩小范围后继续查看。"
        else:
            answer = f"已查询到 {row_count or len(normalized_result)} 条记录，请查看下方结果表。"
        return {
            "final_answer": answer,
            "chart_data": None,
            "table_data": table_data,
            "table_columns": columns,
            "row_count": row_count,
            "truncated": truncated,
            "chat_history": [f"问: {question}\n答: {answer}"],
        }

    answer = llm_complete(
        answer_prompt.format(
            question=question,
            sql_query=sql_query,
            db_result=db_preview,
            data_summary=summary_text,
            evidence_json=_build_evidence_json(columns, normalized_result),
        ),
        task="answer",
    )
    if not answer.strip():
        answer = "结论：结果已返回。\n关键数字：请查看结果表中的聚合字段。\n风险/建议：无。"
    return {
        "final_answer": answer,
        "chart_data": None,
        "table_data": table_data,
        "table_columns": columns,
        "row_count": row_count,
        "truncated": truncated,
        "chat_history": [f"问: {question}\n答: {answer}"],
    }
