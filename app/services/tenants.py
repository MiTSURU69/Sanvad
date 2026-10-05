from ..db import pool

_COLS = ["id", "name", "vertical", "default_language", "allowed_origins",
         "escalation_contact", "extra_forbidden_topics", "status",
         "relevance_threshold", "fallback_message", "extra_instructions"]


def get_tenant(tenant_id: str) -> dict | None:
    with pool.connection() as conn:
        r = conn.execute(
            f"select {', '.join(_COLS)} from tenants where id = %s",
            (tenant_id,),
        ).fetchone()
    if not r:
        return None
    t = dict(zip(_COLS, r))
    if t["status"] != "active":
        return None
    return t


def log_unanswered(tenant_id: str, question: str, best_score: float | None):
    with pool.connection() as conn:
        conn.execute(
            "insert into unanswered (tenant_id, question, best_score) values (%s,%s,%s)",
            (tenant_id, question, best_score),
        )