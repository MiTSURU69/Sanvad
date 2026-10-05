"""Cross-tenant leakage + per-tenant settings tests. Needs DATABASE_URL and `python -m scripts.migrate_m2`.
Leakage rate must be exactly 0."""
import os
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="needs database")

TEST_TENANTS = ("test_a", "test_b", "test_c")


@pytest.fixture(scope="module")
def setup():
    from app.db import pool
    from app.services.embeddings import embed_passages
    pool.open()
    data = {
        "test_a": ["Refunds for shoes are processed within 5 business days.",
                   "Free shipping on orders above 999 rupees.",
                   "रिफंड 5-7 कार्य दिवसों में भेज दिया जाता है।"],
        "test_b": ["Dr. Mehta's clinic is open Monday to Saturday, 9am to 5pm.",
                   "Book a dental checkup through our reception desk.",
                   "Clinic ka consultation fee Rs. 500 hai."],
        "test_c": ["Certificates are issued after you pass the final quiz.",
                   "Course refunds are available within 7 days of purchase.",
                   "Doubts ka jawab mentor 24 ghante mein deta hai."],
    }
    with pool.connection() as conn:
        for tid, texts in data.items():
            conn.execute("delete from chunks where tenant_id=%s", (tid,))
            conn.execute("delete from tenants where id=%s", (tid,))
            conn.execute(
                "insert into tenants (id, name, relevance_threshold) values (%s,%s,%s)",
                (tid, tid, 0.95 if tid == "test_c" else None),
            )
            for t, v in zip(texts, embed_passages(texts)):
                conn.execute(
                    "insert into chunks (tenant_id, content, embedding) values (%s,%s,%s::vector)",
                    (tid, t, v),
                )
    yield data
    with pool.connection() as conn:
        for tid in TEST_TENANTS:
            conn.execute("delete from chunks where tenant_id=%s", (tid,))
            conn.execute("delete from tenants where id=%s", (tid,))
    pool.close()


QUERIES = [
    # English
    "refund policy", "clinic timings", "shipping charges", "dentist appointment",
    "how do I get my certificate", "how to ask a doubt",
    # Hindi
    "रिफंड कब मिलेगा", "क्लिनिक कब खुलता है", "सर्टिफिकेट कैसे मिलेगा",
    # Hinglish
    "mera refund kab milega", "doctor ki fees kitni hai", "certificate kaise milega",
    "order kitne din me aayega",
]


@pytest.mark.parametrize("tenant", TEST_TENANTS)
@pytest.mark.parametrize("q", QUERIES)
def test_no_cross_tenant_leak(setup, tenant, q):
    from app.services.retrieval import retrieve
    own = set(setup[tenant])
    for h in retrieve(tenant, q, k=10):
        assert h["tenant_id"] == tenant
        assert h["content"] in own, "returned content that belongs to another tenant"


def test_every_tenant_only_sees_its_own_chunk_count(setup):
    from app.services.retrieval import retrieve
    for tid, texts in setup.items():
        assert len(retrieve(tid, "anything", k=50)) == len(texts)


@pytest.mark.parametrize("tid", [
    "", "nonexistent", "TEST_A", "test_a ", "%", "test_%",
    "test_a' OR '1'='1", "test_a; drop table chunks;--", "../test_b",
])
def test_malformed_tenant_ids_return_nothing(setup, tid):
    from app.services.tenants import get_tenant
    assert get_tenant(tid) is None


@pytest.mark.parametrize("tid", ["", "nonexistent", "%", "test_a' OR '1'='1"])
def test_chat_route_rejects_unknown_tenants(setup, tid):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from app.main import app
    r = TestClient(app).post("/chat", json={"tenant_id": tid, "message": "refund policy"})
    assert r.status_code == 404


def test_tenant_settings_loaded(setup):
    from app.services.tenants import get_tenant
    assert get_tenant("test_a")["relevance_threshold"] is None
    assert get_tenant("test_c")["relevance_threshold"] == pytest.approx(0.95)


def test_empty_tenant_rejected(setup):
    from app.services.retrieval import retrieve
    with pytest.raises(ValueError):
        retrieve("", "anything")