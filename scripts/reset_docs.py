"""Delete all documents and chunks for one tenant.
Usage: python -m scripts.reset_docs shop_001
"""
import sys

from app.db import pool

tenant = sys.argv[1]
pool.open()
with pool.connection() as conn:
    n_chunks = conn.execute("delete from chunks where tenant_id=%s", (tenant,)).rowcount
    n_docs = conn.execute("delete from documents where tenant_id=%s", (tenant,)).rowcount
print(f"Deleted {n_chunks} chunks and {n_docs} documents for '{tenant}'.")
pool.close()