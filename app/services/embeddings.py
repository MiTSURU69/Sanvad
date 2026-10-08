"""Embedding adapter using the Gemini API. No local model, so no torch in the image."""
import math
import time

import httpx

from ..config import settings

MODEL = "gemini-embedding-001"
DIM = 768
BASE = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}"
BATCH = 20


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _post(path: str, body: dict) -> dict:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    headers = {"x-goog-api-key": settings.gemini_api_key}
    r = None
    for attempt in range(5):
        r = httpx.post(BASE + path, json=body, headers=headers, timeout=30)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(2 ** attempt, 20))
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


def _req(text: str, task: str) -> dict:
    return {
        "model": f"models/{MODEL}",
        "content": {"parts": [{"text": text}]},
        "taskType": task,
        "outputDimensionality": DIM,
    }


def embed_passages(texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        chunk = texts[i:i + BATCH]
        data = _post(":batchEmbedContents",
                     {"requests": [_req(t, "RETRIEVAL_DOCUMENT") for t in chunk]})
        out += [_normalize(e["values"]) for e in data["embeddings"]]
    return out


def embed_query(text: str) -> list[float]:
    data = _post(":embedContent", _req(text, "RETRIEVAL_QUERY"))
    return _normalize(data["embedding"]["values"])