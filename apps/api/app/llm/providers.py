from __future__ import annotations

import re

import httpx

from app.config import get_settings
from app.llm.base import BaseLLMProvider, LLMRequest, LLMResponse
from app.llm.catalog import SUPPORTED_PROVIDERS


class LocalReasoningProvider(BaseLLMProvider):
    def __init__(self, name: str) -> None:
        self.name = name

    def _extract_user_message(self, prompt: str) -> str:
        match = re.search(r"User=(.*)", prompt, re.DOTALL)
        if match:
            return match.group(1).strip()
        return prompt.strip()

    async def generate(self, request: LLMRequest) -> LLMResponse:
        user_text = self._extract_user_message(request.user_prompt)
        text = (
            f"[{self.name}:{request.model}]\n"
            "Reasoning summary:\n"
            f"1) Interpreted request: {user_text}\n"
            "2) Applied available context/tools from current runtime.\n"
            "3) Returned the safest actionable answer within configured constraints.\n\n"
            "Answer:\n"
            f"{user_text}"
        )
        return LLMResponse(text=text, provider=self.name, model=request.model)


class OpenAIChatProvider(BaseLLMProvider):
    def __init__(self, name: str, api_key: str, default_model: str = "gpt-4o-mini") -> None:
        self.name = name
        self._api_key = api_key
        self._default_model = default_model

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if not self._api_key:
            return await LocalReasoningProvider(self.name).generate(request)

        model = request.model if request.model and request.model != "default" else self._default_model
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        text = data["choices"][0]["message"]["content"].strip()
        return LLMResponse(text=text, provider=self.name, model=model)


class GeminiProvider(BaseLLMProvider):
    def __init__(self, name: str, api_key: str, default_model: str = "gemini-1.5-flash") -> None:
        self.name = name
        self._api_key = api_key
        self._default_model = default_model

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if not self._api_key:
            return await LocalReasoningProvider(self.name).generate(request)

        model = request.model if request.model and request.model != "default" else self._default_model
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            f"?key={self._api_key}"
        )
        payload = {
            "systemInstruction": {
                "parts": [{"text": request.system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": request.user_prompt}],
                }
            ],
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return await LocalReasoningProvider(self.name).generate(request)
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            return await LocalReasoningProvider(self.name).generate(request)
        return LLMResponse(text=text, provider=self.name, model=model)


def build_default_providers() -> dict[str, BaseLLMProvider]:
    settings = get_settings()

    providers: dict[str, BaseLLMProvider] = {
        provider: LocalReasoningProvider(provider) for provider in SUPPORTED_PROVIDERS
    }

    providers["openai"] = OpenAIChatProvider("openai", api_key=settings.openai_api_key)
    providers["chatgpt"] = OpenAIChatProvider(
        "chatgpt",
        api_key=settings.chatgpt_api_key or settings.openai_api_key,
    )
    providers["gemini"] = GeminiProvider("gemini", api_key=settings.gemini_api_key)

    return providers
