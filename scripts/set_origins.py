"""Set allowed website origins for a tenant. No origins = allow any website.
Usage:
  python -m scripts.set_origins shop_001 https://shopeasy.example https://www.shopeasy.example
  python -m scripts.set_origins shop_001            # clears the list
"""
import sys

from app.db import pool

tenant, origins = sys.argv[1], [o.rstrip("/") for o in sys.argv[2:]]
pool.open()
with pool.connection() as conn:
    n = conn.execute("update tenants set allowed_origins=%s where id=%s", (origins, tenant)).rowcount
print(f"Updated {n} tenant. allowed_origins = {origins or 'any'}")
pool.close()