"""LLM adapter (Groq, OpenAI-compatible). Add a fallback provider here later."""
import httpx

from ..config import settings

URL = "https://api.groq.com/openai/v1/chat/completions"


async def generate(messages: list[dict], temperature: float = 0.2) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            URL,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            json={"model": settings.llm_model, "messages": messages,
                  "temperature": temperature, "max_tokens": 500},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
