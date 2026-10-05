"""List chunk counts per tenant and source file."""
from app.db import pool

pool.open()
with pool.connection() as conn:
    rows = conn.execute(
        """select tenant_id, metadata->>'source', count(*)
           from chunks group by 1, 2 order by 1, 2"""
    ).fetchall()
    for r in rows:
        print(r)
pool.close()