from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "agentic-platform-api"
    app_env: str = "development"
    log_level: str = "INFO"

    allowed_origins: str = "http://localhost:5173"

    redis_url: str = "redis://localhost:6379/0"
    redis_state_ttl_sec: int = 3600

    rag_store_backend: str = "memory"
    rag_store_file_path: str = "./data/rag_store.json"

    api_keys: str = "dev-key"
    rate_limit_per_minute: int = 10

    max_request_cost_usd: float = 0.02
    default_system_prompt: str = "You are a precise and safe assistant. Use tools only when needed."

    langsmith_tracing: bool = False
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str = ""
    langsmith_project: str = ""

    openai_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    chatgpt_api_key: str = ""

    ros2_bridge_leader_command_url: str = ""
    ros2_bridge_mission_control_url: str = ""
    mavsdk_bridge_leader_command_url: str = ""
    mavsdk_bridge_mission_control_url: str = ""
    default_vision_stream_url: str = ""

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def api_keys_set(self) -> set[str]:
        return {key.strip() for key in self.api_keys.split(",") if key.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
