from __future__ import annotations

from collections import Counter

from app.data.chunking import embed_text
from app.data.models import DocumentChunk


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    return sum(a * b for a, b in zip(vec_a, vec_b))


def _bm25_like_score(query: str, text: str) -> float:
    q_tokens = query.lower().split()
    t_tokens = text.lower().split()
    freq = Counter(t_tokens)
    return sum(freq[token] for token in q_tokens)


def hybrid_search(query: str, docs: list[DocumentChunk], top_k: int = 5) -> list[tuple[DocumentChunk, float]]:
    q_embedding = embed_text(query)
    scored: list[tuple[DocumentChunk, float]] = []
    for doc in docs:
        dense = _cosine_similarity(q_embedding, doc.embedding)
        sparse = _bm25_like_score(query, doc.text)
        score = (0.65 * dense) + (0.35 * sparse)
        scored.append((doc, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:top_k]
