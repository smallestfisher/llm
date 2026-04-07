import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

CONFIG_DIR = Path(__file__).resolve().parent


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_intents() -> List[Dict[str, str]]:
    return _load_json(CONFIG_DIR / "intents.json")


@lru_cache(maxsize=1)
def load_tables() -> Dict[str, Dict[str, Any]]:
    return _load_json(CONFIG_DIR / "tables.json")


@lru_cache(maxsize=1)
def load_lexicon() -> Dict[str, str]:
    return _load_json(CONFIG_DIR / "lexicon.json")


@lru_cache(maxsize=1)
def load_heuristics() -> Dict[str, Any]:
    return _load_json(CONFIG_DIR / "heuristics.json")


@lru_cache(maxsize=1)
def load_runtime() -> Dict[str, Any]:
    return _load_json(CONFIG_DIR / "runtime.json")
