from __future__ import annotations


class MultiAgentCoordinator:
    def route(self, message: str) -> str:
        lowered = message.lower()
        if "search" in lowered or "retrieve" in lowered:
            return "retriever"
        if "plan" in lowered:
            return "planner"
        return "executor"
