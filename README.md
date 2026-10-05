# Sanvad (संवाद)
Multi-tenant, bilingual (English/Hindi/Hinglish) RAG platform for domain-safe customer support.

## Setup
1. Create a Supabase project, open SQL Editor, run `sql/schema.sql`.
2. `cp .env.example .env` and fill DATABASE_URL + GROQ_API_KEY.
3. `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
4. Onboard a tenant:
   ```
   python -m app.ingestion.ingest create-tenant --id shop_001 --name ShopEasy --vertical ecommerce --lang en
   python -m app.ingestion.ingest add --tenant shop_001 --file data/sample_faq_ecommerce.md
   ```
5. Run: `uvicorn app.main:app --reload` then open http://localhost:8000/docs
6. Try `POST /chat` with `{"tenant_id":"shop_001","message":"How long do refunds take?"}`
7. Tests: `pytest -v`

## Calibrating the relevance threshold
E5 cosine scores are compressed (unrelated text often scores 0.7+). Print scores for ~20 in-scope and ~20 off-topic
questions and set RELEVANCE_THRESHOLD between the two clusters. Report this calibration in your thesis.

## Rules
- Chunks are searched ONLY via `services/retrieval.py::retrieve`. Never query `chunks` elsewhere.
- Clients never edit prompts; personas are built in `services/prompts.py`.
