from __future__ import annotations

from dataclasses import dataclass


_PROVIDER_COST_PER_1K_TOKENS = {
    "local": 0.0,
    "openai": 0.005,
    "azure_openai": 0.005,
    "gemini": 0.004,
    "chatgpt": 0.005,
    "claude": 0.006,
    "groq": 0.002,
    "mistral": 0.003,
    "cohere": 0.003,
    "openrouter": 0.004,
    "together": 0.003,
    "deepseek": 0.002,
    "perplexity": 0.005,
    "ollama": 0.0,
}


@dataclass
class CostEstimate:
    estimated_tokens: int
    estimated_cost_usd: float


def estimate_request_cost(message: str, provider: str) -> CostEstimate:
    estimated_tokens = max(1, len(message) // 4)
    per_1k = _PROVIDER_COST_PER_1K_TOKENS.get(provider, 0.006)
    estimated_cost = (estimated_tokens / 1000.0) * per_1k
    return CostEstimate(estimated_tokens=estimated_tokens, estimated_cost_usd=estimated_cost)


def enforce_cost_cap(cost_usd: float, max_cost_usd: float) -> None:
    if cost_usd > max_cost_usd:
        raise ValueError(f"Estimated cost {cost_usd:.6f} exceeds max {max_cost_usd:.6f}")
