from __future__ import annotations

import ast
from collections.abc import Awaitable, Callable

from app.observability import traceable

ToolHandler = Callable[[str], Awaitable[str]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolHandler] = {}

    def register(self, name: str, handler: ToolHandler) -> None:
        self._tools[name] = handler

    async def run(self, name: str, payload: str) -> str:
        handler = self._tools.get(name)
        if handler is None:
            return f"Tool '{name}' not found"
        return await handler(payload)


@traceable(name="tool_math_eval", run_type="tool")
async def math_eval_tool(payload: str) -> str:
    # Safe arithmetic parser for demo tool-calling.
    node = ast.parse(payload, mode="eval")
    allowed = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Num,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.USub,
        ast.UAdd,
    )
    if not all(isinstance(item, allowed) for item in ast.walk(node)):
        return "Invalid expression"
    value = eval(compile(node, "<math_tool>", "eval"), {"__builtins__": {}}, {})
    return str(value)


@traceable(name="tool_web_search_stub", run_type="tool")
async def web_search_stub_tool(payload: str) -> str:
    return f"Stub search result for query: {payload}"
