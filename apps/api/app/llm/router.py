from __future__ import annotations

from app.llm.base import BaseLLMProvider, LLMRequest, LLMResponse
from app.llm.providers import build_default_providers
from app.observability import traceable


class LLMRouter:
    def __init__(self, providers: dict[str, BaseLLMProvider] | None = None) -> None:
        self._providers = providers or build_default_providers()

    def list_providers(self) -> list[str]:
        return sorted(self._providers.keys())

    @traceable(name="llm_router_generate", run_type="llm")
    async def generate(self, provider: str, request: LLMRequest) -> LLMResponse:
        selected = self._providers.get(provider)
        if selected is None:
            selected = self._providers["local"]
        return await selected.generate(request)
