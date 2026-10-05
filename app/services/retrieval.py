"""THE ONLY place chunks are searched. tenant_id is mandatory and always in the WHERE clause.
Never add another code path that queries `chunks` without a tenant filter."""
import numpy as np

from ..db import pool
from ..config import settings
from .embeddings import embed_query


def retrieve(tenant_id: str, query: str, k: int | None = None) -> list[dict]:
    if not tenant_id or not isinstance(tenant_id, str):
        raise ValueError("tenant_id is required for retrieval")
    k = k or settings.top_k
    qv = np.array(embed_query(query))
    with pool.connection() as conn:
        rows = conn.execute(
            """
            select id, tenant_id, content, metadata, 1 - (embedding <=> %s) as score
            from chunks
            where tenant_id = %s
            order by embedding <=> %s
            limit %s
            """,
            (qv, tenant_id, qv, k),
        ).fetchall()
    return [
        {"id": r[0], "tenant_id": r[1], "content": r[2], "metadata": r[3], "score": float(r[4])}
        for r in rows
    ]
