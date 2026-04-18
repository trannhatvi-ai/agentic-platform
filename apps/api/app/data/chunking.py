from __future__ import annotations


def chunk_text(text: str, chunk_size: int = 300, overlap: int = 40) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def embed_text(text: str, dim: int = 16) -> list[float]:
    # Deterministic light-weight embedding for local demo.
    vector = [0.0] * dim
    for idx, ch in enumerate(text):
        vector[idx % dim] += (ord(ch) % 31) / 31.0
    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return vector
    return [value / norm for value in vector]
