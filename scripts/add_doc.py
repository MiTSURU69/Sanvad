import json
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from app.services.embeddings import embed_passages

load_dotenv()

if len(sys.argv) != 3:
    sys.exit("Usage: python -m scripts.add_doc TENANT_ID path/to/file.md")

tenant, path = sys.argv[1], Path(sys.argv[2])
text = path.read_text(encoding="utf-8")

# one chunk per "## " section
chunks, cur = [], []
for line in text.splitlines():
    if line.startswith("## ") and cur:
        chunks.append("\n".join(cur).strip())
        cur = []
    cur.append(line)
if cur:
    chunks.append("\n".join(cur).strip())
chunks = [c for c in chunks if len(c) > 20]
if not chunks:
    sys.exit("No sections found. Each section must start with '## '")

url = next((v for v in os.environ.values() if v.startswith(("postgres://", "postgresql://"))), None)
if not url:
    sys.exit("No Postgres URL found in .env")

vecs = embed_passages(chunks)  # embed first, so a failure here changes nothing in the database

with psycopg.connect(url, prepare_threshold=None) as conn:
    if not conn.execute("select 1 from tenants where id = %s", (tenant,)).fetchone():
        sys.exit(f"Unknown tenant: {tenant}")
    # re-running with the same file name replaces the earlier upload
    conn.execute("delete from documents where tenant_id = %s and filename = %s", (tenant, path.name))
    doc_id = conn.execute(
        "insert into documents (tenant_id, filename) values (%s, %s) returning id",
        (tenant, path.name),
    ).fetchone()[0]
    with conn.cursor() as cur:
        for content, v in zip(chunks, vecs):
            cur.execute(
                "insert into chunks (tenant_id, document_id, content, embedding, metadata) "
                "values (%s, %s, %s, %s::vector, %s::jsonb)",
                (tenant, doc_id, content, str(v), json.dumps({"source": path.name})),
            )
    conn.commit()
print(f"Added {len(chunks)} chunks to {tenant} from {path.name}")