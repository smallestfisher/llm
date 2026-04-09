import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

CONFIG_DIR = Path(__file__).resolve().parent
DOMAINS_DIR = CONFIG_DIR / "domains"


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_optional_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return _load_json(path)


def get_active_domain() -> str:
    return os.getenv("APP_DOMAIN", "boe").strip() or "boe"


def get_domain_config_dir(domain: str | None = None) -> Path:
    return DOMAINS_DIR / (domain or get_active_domain())


def resolve_config_path(filename: str, domain: str | None = None) -> Path:
    domain_path = get_domain_config_dir(domain) / filename
    if domain_path.exists():
        return domain_path
    return CONFIG_DIR / filename


@lru_cache(maxsize=1)
def load_intents() -> List[Dict[str, str]]:
    return _load_json(resolve_config_path("intents.json"))


@lru_cache(maxsize=1)
def load_tables() -> Dict[str, Dict[str, Any]]:
    return _load_json(resolve_config_path("tables.json"))


@lru_cache(maxsize=1)
def load_lexicon() -> Dict[str, str]:
    return _load_json(resolve_config_path("lexicon.json"))


@lru_cache(maxsize=1)
def load_normalization_aliases() -> Dict[str, List[str]]:
    return _load_optional_json(resolve_config_path("normalize_aliases.json"), {})


@lru_cache(maxsize=1)
def load_prompt_context() -> Dict[str, Any]:
    return _load_optional_json(resolve_config_path("prompt_context.json"), {})


@lru_cache(maxsize=1)
def load_heuristics() -> Dict[str, Any]:
    return _load_json(CONFIG_DIR / "heuristics.json")


@lru_cache(maxsize=1)
def load_runtime() -> Dict[str, Any]:
    return _load_json(CONFIG_DIR / "runtime.json")
