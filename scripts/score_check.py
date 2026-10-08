import sys

from app.db import pool
from app.services.retrieval import retrieve

tenant = sys.argv[1]
questions = sys.argv[2:]
if not questions:
    sys.exit('Usage: python -m scripts.score_test TENANT "question 1" "question 2" ...')

pool.open(wait=True, timeout=30)
try:
    for q in questions:
        hits = retrieve(tenant, q)
        if hits:
            print(f"{hits[0]['score']:.3f}  {q}  ->  {hits[0]['content'][:60]!r}")
        else:
            print(f"none   {q}")
finally:
    pool.close()