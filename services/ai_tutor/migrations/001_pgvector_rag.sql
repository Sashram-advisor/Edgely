create extension if not exists vector with schema extensions;

alter table public.document_chunks
  add column if not exists embedding extensions.vector(1536),
  add column if not exists embedding_model text,
  add column if not exists content_hash text,      -- re-embed only when the content changes
  add column if not exists embedded_at timestamptz;

create index if not exists document_chunks_embedding_hnsw
  on public.document_chunks using hnsw (embedding extensions.vector_cosine_ops);
create index if not exists document_chunks_document_id_idx on public.document_chunks(document_id);

alter table public.message_citations
  add column if not exists similarity real,
  add column if not exists rank smallint;

create or replace function public.match_document_chunks(
  query_embedding extensions.vector(1536),
  p_certification_ids bigint[],
  match_count int default 6,
  min_similarity float default 0.25
) returns table (id bigint, document_id bigint, document_title text, exam_domain_id bigint,
                 content text, metadata jsonb, similarity float)
language sql stable
set search_path = public, extensions
as $$
  select c.id, c.document_id, d.title, c.exam_domain_id, c.content, c.metadata,
         1 - (c.embedding <=> query_embedding) as similarity
  from document_chunks c
  join documents d on d.id = c.document_id
  where d.status = 'ready'
    and d.certification_id = any(p_certification_ids)   -- enrollment scoping
    and c.embedding is not null
    and 1 - (c.embedding <=> query_embedding) >= min_similarity
  order by c.embedding <=> query_embedding
  limit match_count;
$$;

revoke execute on function public.match_document_chunks from public, anon, authenticated;
grant execute on function public.match_document_chunks to service_role;