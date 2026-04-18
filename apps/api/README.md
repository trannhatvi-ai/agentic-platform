# FastAPI Backend

## Setup

1. Create a virtual environment: `uv venv`
2. Activate the environment
3. Install dependencies: `uv pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and adjust values
5. Run API: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

## Capabilities

- ReAct-oriented agent runtime with tool registry
- LLM provider router with broad options (local/openai/azure_openai/chatgpt/gemini/claude/groq/mistral/cohere/openrouter/together/deepseek/perplexity/ollama)
- RAG ingest and hybrid retrieval
- Pluggable RAG store backend (`memory` or `file`)
- Guardrails and HITL checks
- Redis-backed session state (stateless API nodes)
- API key auth + rate limiting (10 req/min/user) + cost guard
- Structured JSON request logs
- Runtime metrics endpoint
- UAV mission-state endpoint for the demo dashboard

## Endpoints

- `GET /healthz`
- `GET /readinessz`
- `GET /providers`
- `GET /metrics`
- `GET /api/mission-state`
- `GET /api/health`
- `POST /api/leader-command`
- `POST /api/mission/control`
- `POST /api/sim/telemetry`
- `POST /api/sim/vision`
- `POST /api/sim/map-point`
- `POST /chat`
- `POST /chat/stream`
- `POST /ingest`
- `GET /retrieve`
- `POST /ml/quantize`
- `POST /ml/lora`

## UAV Mission Runtime (Follower)

Mission flow for real execution demo:

1. Assign mission via `POST /api/leader-command`.
2. Start/stop lifecycle via `POST /api/mission/control` with actions: `start`, `pause`, `resume`, `abort`, `reset`.
3. Poll `GET /api/mission-state` for runtime status, checklist, and thought stream.

Example mission assignment:

```bash
curl -X POST http://127.0.0.1:8000/api/leader-command \
	-H "Content-Type: application/json" \
	-d '{"command":"Leader: follow waypoint B7 at 10m and avoid east corridor"}'
```

Example start mission:

```bash
curl -X POST http://127.0.0.1:8000/api/mission/control \
	-H "Content-Type: application/json" \
	-d '{"action":"start"}'
```

### ROS2 + MAVSDK Command Bridge

The API can forward mission commands to your ROS2 and MAVSDK adapters.

Configure in `.env`:

- `ROS2_BRIDGE_LEADER_COMMAND_URL=http://127.0.0.1:9102/bridge/leader-command`
- `ROS2_BRIDGE_MISSION_CONTROL_URL=http://127.0.0.1:9102/bridge/mission-control`
- `MAVSDK_BRIDGE_LEADER_COMMAND_URL=http://127.0.0.1:9101/bridge/leader-command`
- `MAVSDK_BRIDGE_MISSION_CONTROL_URL=http://127.0.0.1:9101/bridge/mission-control`

Run example adapters:

```bash
python tools/mavsdk_bridge_service.py
python tools/ros2_bridge_service.py
```

Optional dependency for MAVSDK bridge:

```bash
pip install mavsdk
```

ROS2 bridge requires `rclpy` from your ROS2 installation (source your ROS2 environment before starting the bridge).

Quick health checks:

```bash
curl http://127.0.0.1:9101/bridge/health
curl http://127.0.0.1:9102/bridge/health
```

Both endpoints return bridge acknowledgements in responses of:

- `POST /api/leader-command`
- `POST /api/mission/control`

## Connecting NVIDIA eSIM Streams

The dashboard now accepts live telemetry, vision, and 2D map points.

Required ingestion endpoints:

- `POST /api/sim/telemetry`
- `POST /api/sim/vision`
- `POST /api/sim/map-point`

For realtime video in UI, send `stream_url` in `POST /api/sim/vision` (HLS/WebRTC gateway URL) and optionally `frame_url` as fallback.

Payload examples:

```json
{"battery_pct": 84.2, "altitude_m": 9.8, "speed_ms": 6.4, "confidence": 0.93}
```

```json
{
	"scene_summary": "Leader path visible, obstacle near north edge",
	"risk_level": "medium",
	"stream_url": "http://localhost:8080/live/index.m3u8",
	"frame_url": "http://localhost:9000/frame.jpg",
	"detected_objects": [{"label": "tree", "distance_m": 12.4, "confidence": 0.9}]
}
```

```json
{"x": 42.1, "y": 37.6, "tag": "uav"}
```

Bridge example script (replace synthetic data source with your eSIM SDK subscriber):

```bash
python tools/esim_bridge_example.py --api-base http://127.0.0.1:8000 --interval 0.25
```

If your stream source is RTSP, expose it through a browser-compatible gateway (HLS/WebRTC) and pass that public URL as `stream_url`.

Example realtime stream push:

```bash
curl -X POST http://127.0.0.1:8000/api/sim/vision \
	-H "Content-Type: application/json" \
	-d '{"scene_summary":"Live eSIM feed","risk_level":"low","stream_url":"http://localhost:8080/live/index.m3u8","detected_objects":[]}'
```

## Required Headers (Protected Routes)

- `x-api-key`: key present in `API_KEYS`
- `x-user-id`: optional user identifier used for rate-limit keying

## LangSmith Tracing

Set these environment variables in `.env` (or shell) to enable tracing:

- `LANGSMITH_TRACING=true`
- `LANGSMITH_ENDPOINT=https://api.smith.langchain.com`
- `LANGSMITH_API_KEY=<your-langsmith-api-key>`
- `LANGSMITH_PROJECT=pr-fresh-roster-48`

Optional if you use OpenAI models:

- `OPENAI_API_KEY=<your-openai-api-key>`