# agentic-platform

Production-minded agentic monorepo: FastAPI backend + React/Vite frontend + Redis state + SSE streaming.

## Features

- Multi-provider LLM router: local, openai, gemini, chatgpt, claude
- Multi-provider LLM router with broad provider catalog and user-selectable options
- Agent runtime with ReAct-style flow and tool-calling skeleton
- LangGraph-compatible workflow boundary
- Data foundation and RAG pipeline with hybrid retrieval (dense + sparse)
- Pluggable RAG storage backend (memory/file) for easy backend swap
- Multi-agent routing, MCP adapter stub, guardrails, HITL gate
- Redis-backed stateless session state
- API key authentication, per-user rate limiting (10 req/min), request cost guard
- Health and readiness endpoints
- Structured JSON logging and graceful shutdown
- Runtime metrics endpoint for basic monitoring
- UAV mission dashboard UI integrated into the main web app
- Quantization and LoRA manager stubs
- Dockerized deployment with multi-stage builds

## Repository Layout

```
agentic-platform/
	apps/
		api/
		web/
	infra/
	README.md
```

## Local Run

1. Start Redis locally (or use Docker compose).
2. Run API:

```bash
cd apps/api
uv venv
# activate venv
uv pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. Run Web:

```bash
cd apps/web
npm install
npm run dev
```

4. Open http://localhost:5173

## Docker Run

```bash
cd infra
docker compose up --build
```

Services:

- API: http://localhost:8000
- Web: http://localhost:5173
- Redis: localhost:6379

## Important Endpoints

- GET /healthz
- GET /readinessz
- GET /providers
- GET /metrics
- GET /api/mission-state
- GET /api/health
- POST /chat
- POST /chat/stream (SSE)
- POST /ingest
- GET /retrieve
- POST /ml/quantize
- POST /ml/lora

Auth headers for protected endpoints:

- x-api-key
- x-user-id (optional; defaults to API key-derived user)