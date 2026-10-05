from app.db import pool
from app.services.retrieval import retrieve

TENANT = "shop_001"

IN_SCOPE = [
    "How long do refunds take?",
    "Is there free shipping?",
    "How can I track my order?",
    "Do you accept UPI?",
    "mera refund kab milega",
    "order kitne din me aayega",
    "रिफंड कितने दिन में मिलता है?",
    "क्या कैश ऑन डिलीवरी मिलता है?",
]

OFF_TOPIC = [
    "Who won the cricket match yesterday?",
    "What is the capital of France?",
    "Write a poem about the moon",
    "I have a headache, what medicine should I take?",
    "Tell me a joke",
    "आज मौसम कैसा है?",
    "bitcoin ka price kya hai",
    "How do I invest in mutual funds?",
]


def best(q):
    hits = retrieve(TENANT, q, k=1)
    return hits[0]["score"] if hits else 0.0


if __name__ == "__main__":
    pool.open()
    print("--- IN SCOPE ---")
    ins = [(best(q), q) for q in IN_SCOPE]
    for s, q in ins:
        print(f"{s:.3f}  {q}")
    print("--- OFF TOPIC ---")
    offs = [(best(q), q) for q in OFF_TOPIC]
    for s, q in offs:
        print(f"{s:.3f}  {q}")
    print(f"\nlowest in-scope : {min(s for s, _ in ins):.3f}")
    print(f"highest off-topic: {max(s for s, _ in offs):.3f}")
    pool.close()