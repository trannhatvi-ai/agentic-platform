from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from redis.asyncio import Redis

from app.auth import resolve_user_id
from app.config import Settings, get_settings
from app.cost_guard import enforce_cost_cap, estimate_request_cost
from app.data.backends import build_document_store
from app.data.rag_pipeline import RAGPipeline
from app.integration import dispatch_leader_command, dispatch_mission_action
from app.llm.router import LLMRouter
from app.logging_config import configure_logging
from app.ml.lora import LoraManager
from app.ml.quantization import QuantizationManager
from app.observability import configure_langsmith
from app.rate_limit import RateLimiter
from app.redis_state import RedisStateStore
from app.monitoring import RuntimeMetrics
from app.uav_state import (
    control_mission,
    get_mission_state,
    ingest_sim_map_point,
    ingest_sim_telemetry,
    ingest_sim_vision,
    mission_state_as_dict,
    set_leader_command,
)
from app.schemas import (
    ChatRequest,
    ChatResponse,
    IngestRequest,
    IngestResponse,
    LeaderCommandRequest,
    LeaderCommandResponse,
    MissionControlRequest,
    MissionControlResponse,
    SimIngestResponse,
    SimMapPointRequest,
    SimTelemetryRequest,
    SimVisionRequest,
    LoraRequest,
    QuantizationRequest,
    RetrievalItem,
    RetrievalResponse,
)
from app.agent.react import ReActAgent

logger = logging.getLogger("agentic-platform")


class AppState:
    redis: Redis | None = None
    state_store: RedisStateStore | None = None
    rate_limiter: RateLimiter | None = None
    rag: RAGPipeline
    agent: ReActAgent
    lora_manager: LoraManager
    quant_manager: QuantizationManager
    metrics: RuntimeMetrics
    redis_ready: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_langsmith(settings)

    app.state.runtime = AppState()
    app.state.runtime.metrics = RuntimeMetrics()
    rag_store = build_document_store(settings.rag_store_backend, settings.rag_store_file_path)
    app.state.runtime.rag = RAGPipeline(store=rag_store)
    app.state.runtime.agent = ReActAgent(llm_router=LLMRouter(), rag=app.state.runtime.rag)
    app.state.runtime.lora_manager = LoraManager()
    app.state.runtime.quant_manager = QuantizationManager()

    try:
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        await redis.ping()
        app.state.runtime.redis = redis
        app.state.runtime.state_store = RedisStateStore(redis, ttl_seconds=settings.redis_state_ttl_sec)
        app.state.runtime.rate_limiter = RateLimiter(redis, limit_per_minute=settings.rate_limit_per_minute)
        app.state.runtime.redis_ready = True
        logger.info("Redis connected")
    except Exception as exc:  # noqa: BLE001
        app.state.runtime.redis_ready = False
        logger.error("Redis unavailable: %s", exc)

    yield

    redis = getattr(app.state.runtime, "redis", None)
    if redis is not None:
        await redis.close()


app = FastAPI(title="Agentic Platform API", version="0.1.0", lifespan=lifespan)
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001
        duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
        request.app.state.runtime.metrics.record(request.url.path, duration_ms, failed=True)
        logger.exception(
            "request_failed",
            extra={"request_id": request_id, "path": request.url.path, "duration_ms": duration_ms},
        )
        return JSONResponse(status_code=500, content={"detail": "internal_error", "request_id": request_id})

    duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
    request.app.state.runtime.metrics.record(request.url.path, duration_ms, failed=False)
    logger.info(
        "request_done",
        extra={"request_id": request_id, "path": request.url.path, "duration_ms": duration_ms},
    )
    response.headers["x-request-id"] = request_id
    return response


def get_runtime(request: Request) -> AppState:
    return request.app.state.runtime


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health")
async def uav_health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readinessz")
async def readinessz(request: Request) -> JSONResponse:
    runtime = get_runtime(request)
    if runtime.redis_ready:
        return JSONResponse(status_code=200, content={"status": "ready"})
    return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "redis_unavailable"})


@app.get("/providers")
async def providers(request: Request) -> dict[str, list[str]]:
    runtime = get_runtime(request)
    return {"providers": runtime.agent.available_providers()}


@app.get("/metrics")
async def metrics(request: Request) -> dict[str, object]:
    runtime = get_runtime(request)
    return runtime.metrics.as_dict()


@app.get("/api/mission-state")
async def mission_state() -> dict[str, object]:
    return mission_state_as_dict(get_mission_state())


@app.post("/api/leader-command", response_model=LeaderCommandResponse)
async def leader_command(payload: LeaderCommandRequest) -> LeaderCommandResponse:
    command = payload.command.strip()
    result = set_leader_command(command)
    bridge = await dispatch_leader_command(
        settings,
        command=str(result["command"]),
        mission_id=str(result["mission_id"]),
        mission_status=str(result["mission_status"]),
    )
    return LeaderCommandResponse(
        accepted=bool(result["accepted"]),
        command=str(result["command"]),
        mission_id=str(result["mission_id"]),
        mission_status=str(result["mission_status"]),
        bridge=bridge,
    )


@app.post("/api/mission/control", response_model=MissionControlResponse)
async def mission_control(payload: MissionControlRequest) -> MissionControlResponse:
    result = control_mission(payload.action)
    bridge = await dispatch_mission_action(
        settings,
        action=payload.action,
        status=str(result["status"]),
        detail=str(result["detail"]),
    )
    return MissionControlResponse(
        accepted=bool(result["accepted"]),
        status=str(result["status"]),
        detail=str(result["detail"]),
        bridge=bridge,
    )


@app.post("/api/sim/telemetry", response_model=SimIngestResponse)
async def sim_telemetry(payload: SimTelemetryRequest) -> SimIngestResponse:
    updated = ingest_sim_telemetry(payload.model_dump())
    return SimIngestResponse(accepted=True, stream="telemetry", updated_at=updated)


@app.post("/api/sim/vision", response_model=SimIngestResponse)
async def sim_vision(payload: SimVisionRequest) -> SimIngestResponse:
    updated = ingest_sim_vision(payload.model_dump())
    return SimIngestResponse(accepted=True, stream="vision", updated_at=updated)


@app.post("/api/sim/map-point", response_model=SimIngestResponse)
async def sim_map_point(payload: SimMapPointRequest) -> SimIngestResponse:
    updated = ingest_sim_map_point(payload.model_dump())
    return SimIngestResponse(accepted=True, stream="map-point", updated_at=updated)


@app.post("/ingest", response_model=IngestResponse)
async def ingest_doc(payload: IngestRequest, request: Request, _: str = Depends(resolve_user_id)) -> IngestResponse:
    runtime = get_runtime(request)
    count = runtime.rag.ingest(namespace=payload.namespace, text=payload.text)
    return IngestResponse(namespace=payload.namespace, chunk_count=count)


@app.get("/retrieve", response_model=RetrievalResponse)
async def retrieve(
    namespace: str,
    query: str,
    request: Request,
    _: str = Depends(resolve_user_id),
) -> RetrievalResponse:
    runtime = get_runtime(request)
    hits = runtime.rag.retrieve(namespace=namespace, query=query, top_k=5)
    return RetrievalResponse(
        namespace=namespace,
        results=[RetrievalItem(text=item.text, source=item.source, score=score) for item, score in hits],
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request, user_id: str = Depends(resolve_user_id)) -> ChatResponse:
    runtime = get_runtime(request)
    if not runtime.redis_ready or runtime.state_store is None or runtime.rate_limiter is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis state backend unavailable")

    allowed = await runtime.rate_limiter.allow(user_id)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    estimate = estimate_request_cost(payload.message, payload.provider)
    try:
        enforce_cost_cap(estimate.estimated_cost_usd, settings.max_request_cost_usd)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    reply = await runtime.agent.run(
        session_id=payload.session_id,
        user_prompt=payload.message,
        provider=payload.provider,
        model=payload.model,
        use_rag=payload.use_rag,
        require_human_approval=payload.require_human_approval,
    )

    session_state = await runtime.state_store.get_session_state(payload.session_id) or {"messages": []}
    session_state["messages"].append({"role": "user", "content": payload.message})
    session_state["messages"].append({"role": "assistant", "content": reply})
    await runtime.state_store.save_session_state(payload.session_id, session_state)

    return ChatResponse(
        session_id=payload.session_id,
        reply=reply,
        provider=payload.provider,
        model=payload.model,
        estimated_cost=round(estimate.estimated_cost_usd, 6),
    )


async def _sse_event(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=True)}\n\n"


@app.post("/chat/stream")
async def chat_stream(payload: ChatRequest, request: Request, user_id: str = Depends(resolve_user_id)) -> StreamingResponse:
    runtime = get_runtime(request)
    if not runtime.redis_ready or runtime.state_store is None or runtime.rate_limiter is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis state backend unavailable")

    allowed = await runtime.rate_limiter.allow(user_id)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    estimate = estimate_request_cost(payload.message, payload.provider)
    try:
        enforce_cost_cap(estimate.estimated_cost_usd, settings.max_request_cost_usd)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    final_text = await runtime.agent.run(
        session_id=payload.session_id,
        user_prompt=payload.message,
        provider=payload.provider,
        model=payload.model,
        use_rag=payload.use_rag,
        require_human_approval=payload.require_human_approval,
    )

    async def generator() -> AsyncGenerator[str, None]:
        yield await _sse_event("start", {"session_id": payload.session_id})
        for token in final_text.split(" "):
            yield await _sse_event("delta", {"delta": token + " "})
            await asyncio.sleep(0.03)
        yield await _sse_event("end", {"done": True, "estimated_cost": round(estimate.estimated_cost_usd, 6)})

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.post("/ml/quantize")
async def quantize(payload: QuantizationRequest, request: Request, _: str = Depends(resolve_user_id)) -> dict[str, str]:
    runtime = get_runtime(request)
    return runtime.quant_manager.start(payload.model_name, payload.method)


@app.post("/ml/lora")
async def train_lora(payload: LoraRequest, request: Request, _: str = Depends(resolve_user_id)) -> dict[str, str]:
    runtime = get_runtime(request)
    return runtime.lora_manager.train(payload.adapter_name, payload.base_model, payload.dataset_ref)
