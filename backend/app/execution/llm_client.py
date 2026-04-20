from __future__ import annotations

import os
import time
from hashlib import sha1

from openai import OpenAI

from app.logging_config import get_logger


logger = get_logger("boe.runtime")
DEBUG_TRACE = os.getenv("DEBUG_TRACE", "0") == "1"
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen3-14B")
LLM_MODEL_ROUTER = os.getenv("LLM_MODEL_ROUTER", LLM_MODEL)
LLM_MODEL_GUARD = os.getenv("LLM_MODEL_GUARD", LLM_MODEL_ROUTER)
LLM_MODEL_SQL = os.getenv("LLM_MODEL_SQL", LLM_MODEL)
LLM_MODEL_REFLECT = os.getenv("LLM_MODEL_REFLECT", LLM_MODEL_SQL)
LLM_MODEL_ANSWER = os.getenv("LLM_MODEL_ANSWER", LLM_MODEL)
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
LLM_MAX_RETRIES = max(1, int(os.getenv("LLM_MAX_RETRIES", "2")))
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-no-key")

_openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)


def _resolve_model(task: str) -> str:
    model_map = {
        "router": LLM_MODEL_ROUTER,
        "guard": LLM_MODEL_GUARD,
        "sql": LLM_MODEL_SQL,
        "reflect": LLM_MODEL_REFLECT,
        "answer": LLM_MODEL_ANSWER,
    }
    return model_map.get(task, LLM_MODEL)


def llm_complete(prompt: str, stream: bool = False, *, task: str = "default") -> str:
    model = _resolve_model(task)
    prompt_hash = sha1(prompt.encode("utf-8")).hexdigest()[:10]
    start = time.perf_counter()
    logger.info(
        "llm_request task={} model={} stream={} prompt={} prompt_chars={} prompt_hash={}",
        task,
        model,
        stream,
        prompt,
        len(prompt),
        prompt_hash,
    )
    response = None
    last_error = None
    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            response = _openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=LLM_TEMPERATURE,
                stream=stream,
                timeout=LLM_TIMEOUT_SECONDS,
            )
            break
        except Exception as exc:
            last_error = exc
            if attempt >= LLM_MAX_RETRIES:
                raise
            logger.warning(
                "llm_request_retry task={} model={} attempt={}/{} err={}",
                task,
                model,
                attempt,
                LLM_MAX_RETRIES,
                str(exc),
            )
            time.sleep(min(0.8 * attempt, 2.0))
    if response is None:
        raise RuntimeError(f"llm response unavailable: {last_error}")
    if not stream:
        content = (response.choices[0].message.content or "").strip()
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "llm_response task={} model={} stream={} response_chars={} elapsed_ms={} prompt_hash={}",
            task,
            model,
            stream,
            len(content),
            elapsed_ms,
            prompt_hash,
        )
        return content

    full_text = ""
    reasoning_started = False
    content_started = False

    def _extract_stream_text(delta, attr_name: str) -> str:
        value = getattr(delta, attr_name, None)
        if not value:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("content") or ""))
                else:
                    parts.append(str(getattr(item, "text", "") or getattr(item, "content", "") or ""))
            return "".join(parts)
        if isinstance(value, dict):
            return str(value.get("text") or value.get("content") or "")
        return str(getattr(value, "text", "") or getattr(value, "content", "") or "")

    for chunk in response:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue
        delta = getattr(choices[0], "delta", None)
        if not delta:
            continue

        reasoning_text = ""
        for field_name in ("reasoning_content", "reasoning", "reasoning_text"):
            reasoning_text = _extract_stream_text(delta, field_name)
            if reasoning_text:
                break

        if DEBUG_TRACE and reasoning_text:
            if not reasoning_started:
                print("\n[REASONING]: ", end="", flush=True)
                reasoning_started = True
            print(reasoning_text, end="", flush=True)

        content_text = _extract_stream_text(delta, "content")
        if content_text:
            if DEBUG_TRACE:
                if reasoning_started and not content_started:
                    print("\n[CONTENT]: ", end="", flush=True)
                content_started = True
                print(content_text, end="", flush=True)
            full_text += content_text

    if DEBUG_TRACE and reasoning_started:
        print("", flush=True)
    if DEBUG_TRACE and content_started:
        print("\n", flush=True)
    content = full_text.strip()
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "llm_response task={} model={} stream={} response_chars={} elapsed_ms={} prompt_hash={}",
        task,
        model,
        stream,
        len(content),
        elapsed_ms,
        prompt_hash,
    )
    return content
