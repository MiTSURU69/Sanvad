import asyncio
import json

import httpx

from ..config import settings

URL = "https://api.groq.com/openai/v1/chat/completions"


async def stream(messages):
    """Yield the reply text piece by piece from Groq. Retries once on 429."""
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
    body = {"model": settings.llm_model, "messages": messages,
            "stream": True, "temperature": 0.2}
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=60.0)) as client:
        for attempt in (1, 2):
            async with client.stream("POST", URL, headers=headers, json=body) as r:
                if r.status_code == 429 and attempt == 1:
                    try:
                        wait = min(float(r.headers.get("retry-after", "2")), 8.0)
                    except ValueError:
                        wait = 2.0
                    await asyncio.sleep(wait)
                    continue
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        piece = json.loads(data)["choices"][0]["delta"].get("content")
                    except (KeyError, IndexError, ValueError):
                        continue
                    if piece:
                        yield piece
                return