import json
import logging
import re
import time
from collections import defaultdict, deque
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..config import settings
from ..services import llm, llm_stream, telegram
from ..services.prompts import FALLBACK, build_system_prompt
from ..services.retrieval import retrieve
from ..services.tenants import get_tenant, log_unanswered

router = APIRouter()
log = logging.getLogger("sanvad")

# --- Simple in-memory rate limiter (per tenant + client IP) ---
RATE_LIMIT = 30
RATE_WINDOW = 60
_hits: dict[str, deque] = defaultdict(deque)


def _rate_limited(key: str) -> bool:
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return True
    q.append(now)
    return False


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    tenant_id: str = Field(max_length=100)
    message: str = Field(min_length=1, max_length=1000)
    history: list[Turn] = Field(default_factory=list, max_length=8)


class ChatResponse(BaseModel):
    answer: str
    answered: bool
    sources: list[str] = []
    escalation_url: str | None = None


# --- Language detection ---
HINGLISH_FALLBACK = "Maaf kijiye, mere paas iski bharosemand jaankari nahi hai. Kya main aapko hamari team se connect kar doon?"

_HINGLISH_WORDS = {
    "kya", "kaise", "kaisa", "kab", "kahan", "kyun", "kyu", "kitna", "kitni", "kitne",
    "hai", "hain", "nahi", "nahin", "mera", "meri", "mere", "mujhe", "aap", "aapka",
    "aapki", "apka", "apki", "karna", "karo", "kare", "karein", "milega", "milta",
    "milegi", "chahiye", "paisa", "wapas", "batao", "bataiye", "bataye", "kaun",
    "kaunsa", "kaunse", "kahaan", "dekhu", "puchu", "kaise", "kab", "abhi", "kitna",
    "samay", "lagega", "lagta", "hoga", "hogi", "kijiye", "dijiye", "bhej", "bheje",
    "tha", "thi", "wala", "wali", "ke", "ki", "ka", "ko",
}
# very common words that are also normal English-looking tokens; need 2+ hits if only these match
_WEAK = {"ke", "ki", "ka", "ko", "tha", "thi", "wala", "wali", "abhi"}


def _is_devanagari(s: str) -> bool:
    return bool(re.search(r"[\u0900-\u097F]", s))


def _is_hinglish(s: str) -> bool:
    words = re.findall(r"[a-z]+", s.lower())
    strong = [w for w in words if w in _HINGLISH_WORDS and w not in _WEAK]
    weak = [w for w in words if w in _WEAK]
    return len(strong) >= 1 or len(weak) >= 2


def _detect_lang(message: str, tenant: dict) -> str:
    if _is_devanagari(message):
        return "hi"
    if _is_hinglish(message):
        return "hinglish"
    return tenant["default_language"]


def _lang_note(lang: str) -> str:
    if lang == "hi":
        return "\n\nREPLY LANGUAGE: Hindi in Devanagari script."
    if lang == "hinglish":
        return ("\n\nREPLY LANGUAGE: Hinglish, meaning Hindi written in English (Roman) letters, "
                "in a casual style like the user's. Do not use Devanagari script.")
    return ""


# --- Reply formatting ---
_STYLE_NOTE = (
    "\n\nFORMAT: Reply in plain conversational text. Do not use tables, headings or horizontal rules. "
    "For lists, put each item on its own line starting with '- '. Keep it concise."
)

# --- Model-side "I can't answer this" detection ---
NO_ANSWER_TAG = "[[NO_ANSWER]]"
_DECLINE_NOTE = (
    "\n\nIf the CONTEXT does not contain the answer to the USER QUESTION, begin your reply with "
    f"exactly {NO_ANSWER_TAG} and then politely say you don't have that information and offer to "
    "connect them with the team. Otherwise answer normally and never write that tag."
)


def _threshold(tenant: dict) -> float:
    t = tenant.get("relevance_threshold")
    return float(t) if t is not None else settings.relevance_threshold


def _fallback(tenant: dict, lang: str) -> str:
    if lang == "hi":
        return FALLBACK["hi"]
    if lang == "hinglish":
        return tenant.get("fallback_message") or HINGLISH_FALLBACK
    return tenant.get("fallback_message") or FALLBACK.get(lang, FALLBACK["en"])


def _origin_allowed(tenant: dict, origin: str | None) -> bool:
    """No Origin header (curl, server-to-server) or no list configured => allowed."""
    allowed = tenant.get("allowed_origins") or []
    if not origin or not allowed:
        return True
    norm = lambda o: o.strip().rstrip("/").lower()
    return norm(origin) in {norm(o) for o in allowed}


def _escalation_url(tenant: dict, question: str) -> str | None:
    """WhatsApp click-to-chat link built from tenant.escalation_contact (digits with country code)."""
    digits = re.sub(r"\D", "", str(tenant.get("escalation_contact") or ""))
    if not (6 <= len(digits) <= 15):
        return None
    text = f"Hi, I need help with {tenant.get('name', 'your service')}. My question: {question[:300]}"
    return f"https://wa.me/{digits}?text={quote(text)}"


def _prepare(req: ChatRequest, request: Request):
    """Shared checks + retrieval. Returns (tenant, lang, messages, hits); messages is None if declined."""
    tenant = get_tenant(req.tenant_id)
    if not tenant:
        raise HTTPException(404, "Unknown tenant")
    if not _origin_allowed(tenant, request.headers.get("origin")):
        raise HTTPException(403, "Origin not allowed for this tenant")

    client = request.client.host if request.client else "unknown"
    if _rate_limited(f"{tenant['id']}:{client}"):
        raise HTTPException(429, "Too many requests")

    hits = retrieve(tenant["id"], req.message)
    best = hits[0]["score"] if hits else None
    lang = _detect_lang(req.message, tenant)

    # Relevance gate: weak retrieval => no LLM call, no hallucination
    if not hits or best < _threshold(tenant):
        log_unanswered(tenant["id"], req.message, best)
        telegram.alert_unanswered(tenant, req.message, best)
        return tenant, lang, None, hits

    context = "\n\n".join(f"[{i+1}] {h['content']}" for i, h in enumerate(hits))
    messages = [{"role": "system", "content": build_system_prompt(tenant)}]
    messages += [t.model_dump() for t in req.history[-4:]]
    messages.append({
        "role": "user",
        "content": (f"CONTEXT:\n<<<\n{context}\n>>>\n\nUSER QUESTION:\n{req.message}"
                    f"{_lang_note(lang)}{_STYLE_NOTE}{_DECLINE_NOTE}"),
    })
    return tenant, lang, messages, hits


def _declined(tenant: dict, lang: str, question: str) -> ChatResponse:
    return ChatResponse(answer=_fallback(tenant, lang), answered=False,
                        escalation_url=_escalation_url(tenant, question))


def _record_model_decline(tenant: dict, question: str, hits: list) -> None:
    best = hits[0]["score"] if hits else None
    try:
        log_unanswered(tenant["id"], question, best)
        telegram.alert_model_declined(tenant, question, best)
    except Exception:
        log.exception("Could not record declined answer")


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    tenant, lang, messages, hits = _prepare(req, request)
    if messages is None:
        return _declined(tenant, lang, req.message)
    try:
        answer = await llm.generate(messages)
    except Exception:
        log.exception("LLM call failed")
        telegram.alert_llm_failure(tenant, req.message)
        raise HTTPException(503, "The assistant is busy, please try again")

    stripped = answer.lstrip()
    if stripped.startswith(NO_ANSWER_TAG):
        text = stripped[len(NO_ANSWER_TAG):].lstrip() or _fallback(tenant, lang)
        _record_model_decline(tenant, req.message, hits)
        return ChatResponse(answer=text, answered=False,
                            escalation_url=_escalation_url(tenant, req.message))

    return ChatResponse(answer=answer, answered=True,
                        sources=[h["metadata"].get("source", "") for h in hits[:3]])


def _ev(d: dict) -> str:
    return json.dumps(d, ensure_ascii=False) + "\n"


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    tenant, lang, messages, hits = _prepare(req, request)

    if messages is None:
        d = _declined(tenant, lang, req.message)

        async def declined():
            yield _ev({"t": "delta", "text": d.answer})
            yield _ev({"t": "done", "answered": False, "escalation_url": d.escalation_url})

        return StreamingResponse(declined(), media_type="application/x-ndjson")

    async def gen():
        buf = ""
        decided = False   # have we seen enough to know if the reply starts with the tag?
        declined = False
        sent = False
        try:
            async for piece in llm_stream.stream(messages):
                if decided:
                    sent = True
                    yield _ev({"t": "delta", "text": piece})
                    continue
                buf += piece
                head = buf.lstrip()
                if len(head) < len(NO_ANSWER_TAG) and NO_ANSWER_TAG.startswith(head):
                    continue  # could still turn into the tag, keep buffering
                decided = True
                if head.startswith(NO_ANSWER_TAG):
                    declined = True
                    head = head[len(NO_ANSWER_TAG):].lstrip()
                if head:
                    sent = True
                    yield _ev({"t": "delta", "text": head})
            if not decided and buf:
                head = buf.lstrip()
                if head.startswith(NO_ANSWER_TAG):
                    declined = True
                    head = head[len(NO_ANSWER_TAG):].lstrip()
                if head:
                    sent = True
                    yield _ev({"t": "delta", "text": head})
        except Exception:
            log.exception("LLM stream failed")
            telegram.alert_llm_failure(tenant, req.message)
            yield _ev({"t": "error"})
            return

        if declined:
            if not sent:
                yield _ev({"t": "delta", "text": _fallback(tenant, lang)})
            _record_model_decline(tenant, req.message, hits)
            yield _ev({"t": "done", "answered": False,
                       "escalation_url": _escalation_url(tenant, req.message)})
        else:
            yield _ev({"t": "done", "answered": True, "escalation_url": None})

    return StreamingResponse(gen(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})