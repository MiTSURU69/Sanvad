import asyncio
import html
import logging
import re
import time
from datetime import datetime, timedelta, timezone

import httpx

from ..config import settings

log = logging.getLogger("sanvad")

COOLDOWN_SECONDS = 3
_last: dict[str, float] = {}
_tasks: set = set()
_IST = timezone(timedelta(hours=5, minutes=30))


def enabled() -> bool:
    return bool(getattr(settings, "telegram_bot_token", "") and getattr(settings, "telegram_chat_id", ""))


async def send(text: str) -> bool:
    """Send an HTML-formatted message. Callers must escape any user text."""
    if not enabled():
        return False
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json={
                "chat_id": settings.telegram_chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
        if r.status_code != 200:
            log.warning("Telegram alert failed: HTTP %s", r.status_code)
            return False
        return True
    except Exception as e:
        log.warning("Telegram alert failed: %s", type(e).__name__)
        return False


def notify(kind: str, tenant_id: str, text: str) -> None:
    """Fire-and-forget alert. Never raises, never slows the chat response."""
    if not enabled():
        return
    key = f"{kind}:{tenant_id}"
    now = time.monotonic()
    if now - _last.get(key, 0) < COOLDOWN_SECONDS:
        return
    _last[key] = now
    try:
        task = asyncio.get_running_loop().create_task(send(text))
    except RuntimeError:
        return
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def _clean(s: str, limit: int = 500) -> str:
    """Collapse whitespace, truncate, then escape for Telegram HTML."""
    s = re.sub(r"\s+", " ", str(s)).strip()
    if len(s) > limit:
        s = s[:limit].rstrip() + "..."
    return html.escape(s)


def _now() -> str:
    return datetime.now(_IST).strftime("%d %b %Y, %I:%M %p IST")


def _shop(tenant: dict) -> str:
    return _clean(tenant.get("name", tenant["id"]), 100)


def alert_unanswered(tenant: dict, question: str, score) -> None:
    if score is None:
        match = "Nothing in the knowledge base matched it."
    else:
        match = f"The closest match in the knowledge base was too weak to trust (score {score:.2f})."
    text = (
        f"A customer on <b>{_shop(tenant)}</b> asked something the bot couldn't answer:\n\n"
        f"<blockquote>{_clean(question)}</blockquote>\n"
        f"{match} They were shown the fallback reply instead.\n\n"
        f"If this is a genuine customer question, it's worth adding the answer to the knowledge base.\n\n"
        f"<i>{_now()} | {html.escape(tenant['id'])}</i>"
    )
    notify("unanswered", tenant["id"], text)


def alert_llm_failure(tenant: dict, question: str) -> None:
    text = (
        f"A customer on <b>{_shop(tenant)}</b> asked a question, but the AI service failed to respond:\n\n"
        f"<blockquote>{_clean(question)}</blockquote>\n"
        f"They saw a \"please try again\" message. Check the server logs and your Groq status, "
        f"and follow up with the customer if needed.\n\n"
        f"<i>{_now()} | {html.escape(tenant['id'])}</i>"
    )
    notify("llm_failure", tenant["id"], text)