from __future__ import annotations

import os

from openai import OpenAI

from app.logging_config import get_logger


logger = get_logger("boe.runtime")
DEBUG_TRACE = os.getenv("DEBUG_TRACE", "0") == "1"
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen3-14B")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-no-key")

_openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)


def llm_complete(prompt: str, stream: bool = False) -> str:
    response = _openai_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=LLM_TEMPERATURE,
        stream=stream,
    )
    logger.info(f"============== stream: {stream}, prompt: {prompt}, result_text: {response}")
    if not stream:
        return (response.choices[0].message.content or "").strip()
        
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
            if DEBUG_TRACE and reasoning_started and not content_started:
                print("\n[CONTENT]: ", end="", flush=True)
            elif not DEBUG_TRACE and not content_started:
                print("\n[STREAMING]: ", end="", flush=True)
            content_started = True
            print(content_text, end="", flush=True)
            full_text += content_text

    if DEBUG_TRACE and reasoning_started:
        print("", flush=True)
    if content_started:
        print("\n", flush=True)
    logger.info(f"full_text: {full_text}")
    return full_text.strip()
