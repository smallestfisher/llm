from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_tables() -> dict[str, dict[str, Any]]:
    return _load_json(CONFIG_DIR / "tables.json")


@lru_cache(maxsize=1)
def load_heuristics() -> dict[str, Any]:
    return _load_json(CONFIG_DIR / "heuristics.json")


@lru_cache(maxsize=1)
def load_intents() -> list[dict[str, str]]:
    return _load_json(CONFIG_DIR / "intents.json")


@lru_cache(maxsize=1)
def load_lexicon() -> dict[str, str]:
    return _load_json(CONFIG_DIR / "lexicon.json")


def load_tables_registry() -> dict[str, dict[str, Any]]:
    return load_tables()
