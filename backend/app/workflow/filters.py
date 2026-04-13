from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.router.filter_extractor import extract_shared_filters  # noqa: E402

__all__ = ["extract_shared_filters"]
