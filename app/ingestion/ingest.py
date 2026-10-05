"""CLI for onboarding.
  python -m app.ingestion.ingest create-tenant --id shop_001 --name "ShopEasy" --vertical ecommerce --lang en
  python -m app.ingestion.ingest create-tenant --id clinic_001 --name "SmileCare Clinic" --vertical healthcare --lang en --threshold 0.81 --fallback "Please call our front desk." --instructions "Never give medical advice."
  python -m app.ingestion.ingest add --tenant shop_001 --file faq.md --faq

Run `python -m scripts.migrate_m2` once before using --threshold/--fallback/--instructions.
"""
import argparse
import json
import re
from pathlib import Path

from ..db import pool
from ..services.embeddings import embed_passages


def read_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        text = "\n".join(p.extract_text() or "" for p in PdfReader(str(path)).pages)
        if len(text.strip()) < 50:
            print("WARNING: little/no text extracted (scanned or font-encoded PDF?). OCR fallback needed.")
        return text
    return path.read_text(encoding="utf-8")


def chunk(text: str, max_chars: int = 800, overlap: int = 120) -> list[str]:
    """Paragraph-aware chunking; long paragraphs split on sentence ends (incl. Hindi danda)."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 1 <= max_chars:
            cur = f"{cur}\n{p}".strip()
            continue
        if cur:
            chunks.append(cur)
        if len(p) > max_chars:
            cur = ""
            for s in re.split(r"(?<=[.!?।])\s+", p):
                if cur and len(cur) + len(s) + 1 > max_chars:
                    chunks.append(cur)
                    cur = cur[-overlap:] + " " + s
                else:
                    cur = f"{cur} {s}".strip()
        else:
            cur = (chunks[-1][-overlap:] + "\n" + p) if chunks else p
    if cur:
        chunks.append(cur)
    return chunks


def chunk_faq(text: str) -> list[str]:
    """One chunk per blank-line-separated block (use for Q&A-style FAQs)."""
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def create_tenant(a):
    with pool.connection() as conn:
        conn.execute(
            """insert into tenants (id, name, vertical, default_language, escalation_contact,
                                    relevance_threshold, fallback_message, extra_instructions)
               values (%s,%s,%s,%s,%s,%s,%s,%s)
               on conflict (id) do update set name=excluded.name, vertical=excluded.vertical,
               default_language=excluded.default_language, escalation_contact=excluded.escalation_contact,
               relevance_threshold=excluded.relevance_threshold,
               fallback_message=excluded.fallback_message,
               extra_instructions=excluded.extra_instructions""",
            (a.id, a.name, a.vertical, a.lang, a.contact,
             a.threshold, a.fallback, a.instructions),
        )
    print(f"Tenant '{a.id}' ready.")


def add_document(a):
    path = Path(a.file)
    text = read_file(path)
    chunks = chunk_faq(text) if a.faq else chunk(text)
    vecs = embed_passages(chunks)
    with pool.connection() as conn:
        doc_id = conn.execute(
            "insert into documents (tenant_id, filename) values (%s,%s) returning id",
            (a.tenant, path.name),
        ).fetchone()[0]
        for c, v in zip(chunks, vecs):
            conn.execute(
                "insert into chunks (tenant_id, document_id, content, embedding, metadata) "
                "values (%s,%s,%s,%s::vector,%s::jsonb)",
                (a.tenant, doc_id, c, v, json.dumps({"source": path.name})),
            )
    print(f"Ingested {len(chunks)} chunks from {path.name} into '{a.tenant}'.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("create-tenant")
    t.add_argument("--id", required=True)
    t.add_argument("--name", required=True)
    t.add_argument("--vertical", default="general")
    t.add_argument("--lang", default="en")
    t.add_argument("--contact", default=None)
    t.add_argument("--threshold", type=float, default=None)
    t.add_argument("--fallback", default=None)
    t.add_argument("--instructions", default=None)
    d = sub.add_parser("add")
    d.add_argument("--tenant", required=True)
    d.add_argument("--file", required=True)
    d.add_argument("--faq", action="store_true")
    args = ap.parse_args()
    pool.open()
    create_tenant(args) if args.cmd == "create-tenant" else add_document(args)
    pool.close()