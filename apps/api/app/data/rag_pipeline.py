from __future__ import annotations

import hashlib

from app.data.backends import DocumentStore, InMemoryDocumentStore
from app.data.chunking import chunk_text, embed_text
from app.data.hybrid_search import hybrid_search
from app.data.models import DocumentChunk


class RAGPipeline:
    def __init__(self, store: DocumentStore | None = None) -> None:
        self._store = store or InMemoryDocumentStore()

    def ingest(self, namespace: str, text: str, source: str = "manual") -> int:
        chunks = chunk_text(text)
        for chunk in chunks:
            chunk_id = hashlib.sha1(f"{namespace}:{chunk}".encode("utf-8")).hexdigest()[:16]
            item = DocumentChunk(
                chunk_id=chunk_id,
                namespace=namespace,
                text=chunk,
                source=source,
                embedding=embed_text(chunk),
            )
            self._store.add(item)
        return len(chunks)

    def retrieve(self, namespace: str, query: str, top_k: int = 5) -> list[tuple[DocumentChunk, float]]:
        docs = self._store.all(namespace)
        return hybrid_search(query, docs, top_k=top_k)
