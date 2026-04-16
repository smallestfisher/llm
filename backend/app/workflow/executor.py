from __future__ import annotations

from typing import Callable

from app.workflow.orchestrator import get_compiled_workflow
from app.workflow.state import RouteDecision


async def execute_chat_workflow(
    question: str,
    chat_history: list[str],
    initial_decision: RouteDecision | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    on_event: Callable[[str, dict], None] | None = None,
) -> dict:
    workflow = await get_compiled_workflow()
    return await workflow.ainvoke(
        {"question": question, "chat_history": chat_history, "initial_decision": initial_decision},
        config={"is_cancelled": is_cancelled, "on_event": on_event},
    )
