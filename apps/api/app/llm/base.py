from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LLMRequest:
    system_prompt: str
    user_prompt: str
    model: str


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str


class BaseLLMProvider:
    name: str

    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError
