from __future__ import annotations

from typing import Optional, Sequence


def build_history_from_messages(messages: Sequence[object]) -> list[str]:
    history: list[str] = []
    pending_question: Optional[str] = None
    for message in messages:
        if getattr(message, "role", None) == "user":
            pending_question = getattr(message, "content", "")
            continue
        if getattr(message, "role", None) == "assistant" and pending_question:
            history.append(f"问: {pending_question}\n答: {getattr(message, 'content', '')}")
            pending_question = None
    return history


def build_regenerate_seed_history_from_messages(messages: Sequence[object]) -> tuple[list[str], object | None, object | None]:
    last_user_index = None
    last_assistant_index = None
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if last_assistant_index is None and getattr(message, "role", None) == "assistant":
            last_assistant_index = index
            continue
        if getattr(message, "role", None) == "user":
            last_user_index = index
            break
    if last_user_index is None:
        return [], None, None
    last_user = messages[last_user_index]
    if last_assistant_index is None or last_assistant_index < last_user_index:
        return build_history_from_messages(messages[:last_user_index]), last_user, None
    history = build_history_from_messages(messages[:last_user_index])
    return history, last_user, messages[last_assistant_index]


def build_regenerate_seed_history_for_message(messages: Sequence[object], assistant_message_id: int) -> tuple[list[str], object | None, object | None]:
    target_index = None
    for index, message in enumerate(messages):
        if getattr(message, "id", None) == assistant_message_id and getattr(message, "role", None) == "assistant":
            target_index = index
            break
    if target_index is None:
        return [], None, None
    user_index = None
    for index in range(target_index - 1, -1, -1):
        if getattr(messages[index], "role", None) == "user":
            user_index = index
            break
    if user_index is None:
        return [], None, None
    history = build_history_from_messages(messages[:user_index])
    return history, messages[user_index], messages[target_index]
