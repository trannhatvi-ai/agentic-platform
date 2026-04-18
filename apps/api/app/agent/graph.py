from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypedDict


class AgentState(TypedDict):
    message: str
    tool_result: str


class AgentGraph:
    def __init__(self, tool_node: Callable[[str], Awaitable[str]]) -> None:
        self._tool_node = tool_node

    async def run(self, message: str) -> AgentState:
        # This intentionally keeps the graph abstraction thin while remaining LangGraph-compatible.
        tool_result = await self._tool_node(message)
        return {"message": message, "tool_result": tool_result}
