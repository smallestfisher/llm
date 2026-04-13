from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.workflow.orchestrator import get_compiled_workflow  # noqa: E402


async def execute_chat_workflow(question: str, chat_history: list[str]) -> dict:
    workflow = await get_compiled_workflow()
    return await workflow.ainvoke({"question": question, "chat_history": chat_history}, config={})
