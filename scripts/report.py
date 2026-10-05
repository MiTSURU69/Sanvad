"""Per-tenant overview and unanswered-question report.
Usage:
  python -m scripts.report                 # all tenants summary
  python -m scripts.report shop_001        # top unanswered questions for one tenant
"""
import sys

from app.config import settings
from app.db import pool

pool.open()
with pool.connection() as conn:
    if len(sys.argv) == 1:
        rows = conn.execute(
            """select t.id, t.name, t.vertical, t.relevance_threshold,
                      (select count(*) from chunks c where c.tenant_id = t.id),
                      (select count(*) from unanswered u where u.tenant_id = t.id)
               from tenants t order by t.id"""
        ).fetchall()
        print(f"{'id':<14}{'name':<20}{'vertical':<12}{'threshold':<11}{'chunks':<8}{'unanswered'}")
        for r in rows:
            thr = r[3] if r[3] is not None else f"{settings.relevance_threshold}*"
            print(f"{r[0]:<14}{r[1]:<20}{r[2]:<12}{str(thr):<11}{r[4]:<8}{r[5]}")
        print("\n* = inherited from .env default")
    else:
        tid = sys.argv[1]
        rows = conn.execute(
            """select question, count(*) as n, max(best_score) as best
               from unanswered where tenant_id = %s
               group by question order by n desc, best desc limit 25""",
            (tid,),
        ).fetchall()
        print(f"Top unanswered questions for '{tid}':\n")
        for q, n, best in rows:
            score = f"{best:.3f}" if best is not None else "none"
            print(f"{n:>3}x  best_score={score}  {q}")
        if not rows:
            print("(none logged)")
pool.close()