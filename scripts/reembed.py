import os
import sys

import psycopg
from dotenv import load_dotenv

from app.services.embeddings import embed_passages

load_dotenv()
url = next((v for v in os.environ.values() if v.startswith(("postgres://", "postgresql://"))), None)
if not url:
    sys.exit("No Postgres URL found in .env")

with psycopg.connect(url, prepare_threshold=None) as conn:
    rows = conn.execute("select id, content from chunks where embedding is null order by id").fetchall()
    print(f"{len(rows)} chunks to embed")
    for i in range(0, len(rows), 20):
        batch = rows[i:i + 20]
        vecs = embed_passages([r[1] for r in batch])
        with conn.cursor() as cur:
            for (cid, _), v in zip(batch, vecs):
                cur.execute("update chunks set embedding = %s::vector where id = %s", (str(v), cid))
        conn.commit()
        print(f"{min(i + 20, len(rows))}/{len(rows)}")
print("done")