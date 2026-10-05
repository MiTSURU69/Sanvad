"""Embedding adapter. E5 models need 'query: ' / 'passage: ' prefixes."""
from functools import lru_cache

from ..config import settings


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(settings.embedding_model)


def embed_passages(texts: list[str]) -> list[list[float]]:
    return _model().encode([f"passage: {t}" for t in texts], normalize_embeddings=True).tolist()


def embed_query(text: str) -> list[float]:
    return _model().encode(f"query: {text}", normalize_embeddings=True).tolist()
