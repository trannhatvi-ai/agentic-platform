from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DocumentChunk:
    chunk_id: str
    namespace: str
    text: str
    source: str
    embedding: list[float]
