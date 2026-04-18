from __future__ import annotations

BLOCKED_TOKENS = {"malware", "exploit", "credential dump"}


def validate_input(message: str) -> None:
    lowered = message.lower()
    for token in BLOCKED_TOKENS:
        if token in lowered:
            raise ValueError("Input blocked by guardrails")


def validate_output(message: str) -> None:
    if len(message) > 6000:
        raise ValueError("Output blocked by guardrails")
