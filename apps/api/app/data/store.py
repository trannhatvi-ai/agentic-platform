from __future__ import annotations

from app.data.models import DocumentChunk


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._items: list[DocumentChunk] = []

    def add(self, item: DocumentChunk) -> None:
        self._items.append(item)

    def all(self, namespace: str) -> list[DocumentChunk]:
        return [item for item in self._items if item.namespace == namespace]
