from __future__ import annotations


class LoraManager:
    def __init__(self) -> None:
        self._runs: list[dict[str, str]] = []

    def train(self, adapter_name: str, base_model: str, dataset_ref: str) -> dict[str, str]:
        run = {
            "status": "scheduled",
            "adapter": adapter_name,
            "base_model": base_model,
            "dataset": dataset_ref,
            "note": "Stub manager. Replace with real LoRA trainer (PEFT/QLoRA).",
        }
        self._runs.append(run)
        return run
