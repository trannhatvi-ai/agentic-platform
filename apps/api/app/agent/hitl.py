from __future__ import annotations


def needs_human_approval(user_prompt: str, explicit_flag: bool) -> bool:
    if explicit_flag:
        return True
    lowered = user_prompt.lower()
    return any(token in lowered for token in ["delete", "transfer money", "drop database"])
