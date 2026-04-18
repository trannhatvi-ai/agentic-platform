from __future__ import annotations

from app.agent.graph import AgentGraph
from app.agent.guardrails import validate_input, validate_output
from app.agent.hitl import needs_human_approval
from app.agent.multi_agent import MultiAgentCoordinator
from app.agent.prompts import BASE_SYSTEM_PROMPT
from app.agent.tools import ToolRegistry, math_eval_tool, web_search_stub_tool
from app.data.rag_pipeline import RAGPipeline
from app.llm.base import LLMRequest
from app.llm.router import LLMRouter
from app.observability import traceable


class ReActAgent:
    def __init__(self, llm_router: LLMRouter, rag: RAGPipeline) -> None:
        self._llm_router = llm_router
        self._rag = rag
        self._coordinator = MultiAgentCoordinator()
        self._tools = ToolRegistry()
        self._tools.register("math_eval", math_eval_tool)
        self._tools.register("web_search", web_search_stub_tool)
        self._graph = AgentGraph(self._run_default_tool)

    def available_providers(self) -> list[str]:
        return self._llm_router.list_providers()

    async def _run_default_tool(self, message: str) -> str:
        if message.startswith("calc:"):
            return await self._tools.run("math_eval", message.replace("calc:", "", 1).strip())
        if message.startswith("search:"):
            return await self._tools.run("web_search", message.replace("search:", "", 1).strip())
        return "no_tool"

    @traceable(name="react_agent_run", run_type="chain")
    async def run(
        self,
        *,
        session_id: str,
        user_prompt: str,
        provider: str,
        model: str,
        use_rag: bool,
        require_human_approval: bool,
    ) -> str:
        validate_input(user_prompt)

        if needs_human_approval(user_prompt, require_human_approval):
            return "Action requires human approval (HITL gate)."

        role = self._coordinator.route(user_prompt)

        rag_context = ""
        if use_rag:
            hits = self._rag.retrieve(namespace=session_id, query=user_prompt, top_k=3)
            if hits:
                rag_context = "\n".join(f"- {item.text}" for item, _ in hits)

        graph_state = await self._graph.run(user_prompt)

        prompt = (
            f"Role={role}\n"
            f"ToolResult={graph_state['tool_result']}\n"
            f"RAGContext={rag_context if rag_context else 'none'}\n"
            f"User={user_prompt}"
        )

        result = await self._llm_router.generate(
            provider=provider,
            request=LLMRequest(system_prompt=BASE_SYSTEM_PROMPT, user_prompt=prompt, model=model),
        )
        validate_output(result.text)
        return result.text
