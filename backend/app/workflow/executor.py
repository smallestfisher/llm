from __future__ import annotations

from app.workflow.orchestrator import get_compiled_workflow


async def execute_chat_workflow(question: str, chat_history: list[str]) -> dict:
    workflow = await get_compiled_workflow()
    return await workflow.ainvoke({"question": question, "chat_history": chat_history}, config={})
