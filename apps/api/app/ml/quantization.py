from __future__ import annotations


class QuantizationManager:
    def __init__(self) -> None:
        self._jobs: list[dict[str, str]] = []

    def start(self, model_name: str, method: str) -> dict[str, str]:
        job = {
            "status": "queued",
            "model": model_name,
            "method": method,
            "note": "Stub manager. Replace with real quantization pipeline.",
        }
        self._jobs.append(job)
        return job
