"""Milestone 2 migration: per-tenant settings. Safe to run more than once."""
from app.db import pool

pool.open()
with pool.connection() as conn:
    conn.execute("alter table tenants add column if not exists relevance_threshold real")
    conn.execute("alter table tenants add column if not exists fallback_message text")
    conn.execute("alter table tenants add column if not exists extra_instructions text")
print("Migration done.")
pool.close()