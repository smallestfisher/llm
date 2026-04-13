from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.router.intent_router import route_question  # noqa: E402
from core.runtime.state import RouteDecision  # noqa: E402


def decide_route(question: str) -> RouteDecision:
    return route_question(question)
