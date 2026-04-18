from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from app.data.models import DocumentChunk


class DocumentStore(Protocol):
    def add(self, item: DocumentChunk) -> None:
        ...

    def all(self, namespace: str) -> list[DocumentChunk]:
        ...


class InMemoryDocumentStore:
    def __init__(self) -> None:
        self._items: list[DocumentChunk] = []

    def add(self, item: DocumentChunk) -> None:
        self._items.append(item)

    def all(self, namespace: str) -> list[DocumentChunk]:
        return [item for item in self._items if item.namespace == namespace]


class JsonFileDocumentStore:
    def __init__(self, file_path: str) -> None:
        self._path = Path(file_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: list[DocumentChunk] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._cache = []
            return
        data = json.loads(self._path.read_text(encoding="utf-8"))
        self._cache = [DocumentChunk(**item) for item in data]

    def _save(self) -> None:
        payload = [item.__dict__ for item in self._cache]
        self._path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")

    def add(self, item: DocumentChunk) -> None:
        self._cache.append(item)
        self._save()

    def all(self, namespace: str) -> list[DocumentChunk]:
        return [item for item in self._cache if item.namespace == namespace]


def build_document_store(backend: str, file_path: str) -> DocumentStore:
    if backend == "file":
        return JsonFileDocumentStore(file_path=file_path)
    return InMemoryDocumentStore()
