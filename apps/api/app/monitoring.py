from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RuntimeMetrics:
    total_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    route_hits: dict[str, int] = field(default_factory=dict)

    def record(self, path: str, duration_ms: float, failed: bool) -> None:
        self.total_requests += 1
        self.total_latency_ms += duration_ms
        self.route_hits[path] = self.route_hits.get(path, 0) + 1
        if failed:
            self.failed_requests += 1

    @property
    def avg_latency_ms(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests

    def as_dict(self) -> dict[str, object]:
        return {
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "route_hits": self.route_hits,
        }
