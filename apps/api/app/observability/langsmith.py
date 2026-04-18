from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("agentic-platform.langsmith")

try:
    from langsmith import traceable as _langsmith_traceable
except Exception:  # noqa: BLE001
    _langsmith_traceable = None


def configure_langsmith(settings: Any) -> None:
    if not getattr(settings, "langsmith_tracing", False):
        return

    os.environ["LANGSMITH_TRACING"] = "true"
    if getattr(settings, "langsmith_endpoint", ""):
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    if getattr(settings, "langsmith_api_key", ""):
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    if getattr(settings, "langsmith_project", ""):
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project

    logger.info("LangSmith tracing enabled")


def traceable(name: str, run_type: str = "chain") -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if _langsmith_traceable is None:
            return func
        return _langsmith_traceable(name=name, run_type=run_type)(func)

    return decorator
