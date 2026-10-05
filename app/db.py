from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector

from .config import settings

pool = ConnectionPool(
    settings.database_url, min_size=1, max_size=5, open=False, configure=register_vector
)
