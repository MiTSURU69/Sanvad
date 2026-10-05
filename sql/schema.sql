create extension if not exists vector;

create table if not exists tenants (
  id text primary key,
  name text not null,
  vertical text not null default 'general',
  default_language text not null default 'en',       -- 'en' | 'hi'
  allowed_origins text[] not null default '{}',      -- enforced in Milestone 4
  escalation_contact text,
  extra_forbidden_topics text[] not null default '{}',
  status text not null default 'active',
  created_at timestamptz not null default now()
);

create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null references tenants(id) on delete cascade,
  filename text not null,
  created_at timestamptz not null default now()
);

create table if not exists chunks (
  id bigserial primary key,
  tenant_id text not null references tenants(id) on delete cascade,
  document_id uuid references documents(id) on delete cascade,
  content text not null,
  embedding vector(384) not null,
  metadata jsonb not null default '{}'
);
create index if not exists chunks_tenant_idx on chunks(tenant_id);
create index if not exists chunks_embedding_idx on chunks using hnsw (embedding vector_cosine_ops);

-- questions the bot could not answer; feeds the client dashboard later
create table if not exists unanswered (
  id bigserial primary key,
  tenant_id text not null references tenants(id) on delete cascade,
  question text not null,
  best_score real,
  created_at timestamptz not null default now()
);
