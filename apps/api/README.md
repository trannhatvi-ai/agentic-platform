# FastAPI Backend

## Setup
1. Create a virtual environment: `uv venv`
2. Install dependencies: `uv pip install -r requirements.txt`
3. Run the application: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

## Endpoints
- `GET /healthz`: Check health status
- `POST /chat`: Chat endpoint
- `GET /chat/stream`: Stream chat responses
- `POST /chat/stream`: Stream chat responses (SSE)