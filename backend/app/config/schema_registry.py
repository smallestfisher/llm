from __future__ import annotations

import json
from pathlib import Path


TABLES_JSON_PATH = Path(__file__).resolve().parents[3] / "core" / "config" / "tables.json"


def load_tables_registry() -> dict:
    with TABLES_JSON_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)
