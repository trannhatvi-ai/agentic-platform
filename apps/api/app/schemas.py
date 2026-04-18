from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=3)
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    provider: Literal[
        "local",
        "openai",
        "azure_openai",
        "chatgpt",
        "gemini",
        "claude",
        "groq",
        "mistral",
        "cohere",
        "openrouter",
        "together",
        "deepseek",
        "perplexity",
        "ollama",
    ] = "local"
    model: str = "default"
    use_rag: bool = True
    require_human_approval: bool = False


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    provider: str
    model: str
    estimated_cost: float


class IngestRequest(BaseModel):
    namespace: str = Field(default="default", min_length=1)
    text: str = Field(min_length=1)


class IngestResponse(BaseModel):
    namespace: str
    chunk_count: int


class RetrievalItem(BaseModel):
    text: str
    source: str
    score: float


class RetrievalResponse(BaseModel):
    namespace: str
    results: list[RetrievalItem]


class LoraRequest(BaseModel):
    adapter_name: str = Field(min_length=1)
    base_model: str = Field(min_length=1)
    dataset_ref: str = Field(min_length=1)


class QuantizationRequest(BaseModel):
    model_name: str = Field(min_length=1)
    method: Literal["int8", "int4", "awq", "gptq"]


class LeaderCommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=500)


class LeaderCommandResponse(BaseModel):
    accepted: bool
    command: str
    mission_id: str
    mission_status: str
    bridge: dict[str, object] = Field(default_factory=dict)


class MissionControlRequest(BaseModel):
    action: Literal["start", "pause", "resume", "abort", "reset"]


class MissionControlResponse(BaseModel):
    accepted: bool
    status: str
    detail: str
    bridge: dict[str, object] = Field(default_factory=dict)


class SimTelemetryRequest(BaseModel):
    battery_pct: float = Field(ge=0, le=100)
    altitude_m: float = Field(ge=0)
    speed_ms: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)


class SimVisionObject(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    distance_m: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)


class SimVisionRequest(BaseModel):
    scene_summary: str = Field(min_length=1, max_length=500)
    risk_level: Literal["low", "medium", "high"]
    frame_url: str | None = None
    stream_url: str | None = None
    detected_objects: list[SimVisionObject] = Field(default_factory=list)


class SimMapPointRequest(BaseModel):
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    tag: Literal["uav", "waypoint", "obstacle", "trail"] = "trail"


class SimIngestResponse(BaseModel):
    accepted: bool
    stream: str
    updated_at: int
