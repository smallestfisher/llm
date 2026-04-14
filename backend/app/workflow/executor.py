from __future__ import annotations

from typing import Callable

from app.workflow.orchestrator import get_compiled_workflow


async def execute_chat_workflow(
    question: str,
    chat_history: list[str],
    is_cancelled: Callable[[], bool] | None = None,
) -> dict:
    workflow = await get_compiled_workflow()
    return await workflow.ainvoke(
        {"question": question, "chat_history": chat_history},
        config={"is_cancelled": is_cancelled},
    )
