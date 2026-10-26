"""Set a tenant's relevance threshold only.
Usage: python -m scripts.set_threshold shop_001 0.66     (use 'none' to inherit .env)
"""
import sys

from app.db import pool

tenant, val = sys.argv[1], sys.argv[2]
thr = None if val.lower() == "none" else float(val)
pool.open()
with pool.connection() as conn:
    n = conn.execute("update tenants set relevance_threshold=%s where id=%s", (thr, tenant)).rowcount
print(f"Updated {n} tenant. relevance_threshold = {thr}")
pool.close()