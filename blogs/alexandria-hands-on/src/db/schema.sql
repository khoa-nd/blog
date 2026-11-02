-- Alexandria schema. Safe to run more than once (python -m alexandria db-init).
-- Works on Supabase and on plain Postgres 16. Tables are closed to the public API
-- (row level security with no policies); the console and the daily pages talk to
-- the database only through the alx_* functions at the end, which check the owner key.

create extension if not exists vector;

do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
end $$;

create table if not exists app_owner (
  id int primary key default 1 check (id = 1),
  key_hash text not null
);

create table if not exists control (
  key text primary key,
  value text not null
);

create table if not exists taste_facet (
  id serial primary key,
  slug text unique not null,
  name text not null,
  priority real not null check (priority between 0 and 1),
  keywords text[] not null default '{}',
  status text not null default 'active' check (status in ('active', 'paused', 'removed')),
  created_at timestamptz not null default now()
);

create table if not exists taste_event (
  id bigserial primary key,
  facet_slug text,
  kind text not null check (kind in ('add', 'reweight', 'pause', 'resume', 'remove', 'note')),
  payload jsonb not null default '{}',
  source text not null check (source in ('seed', 'console', 'reflection', 'comment')),
  at timestamptz not null default now()
);

create table if not exists profile_version (
  id serial primary key,
  text text not null,
  facets jsonb not null,
  created_at timestamptz not null default now(),
  approved_at timestamptz
);

create table if not exists tracked_site (
  id serial primary key,
  name text not null,
  url text unique not null,
  kind text not null check (kind in ('bookstore', 'publisher', 'prize', 'review')),
  language text not null default 'en',
  watch text[] not null default '{}',
  link_pattern text,
  search_template text,
  mode text not null default 'pending' check (mode in ('pending', 'crawl', 'link-only')),
  mode_reason text,
  delay_s int not null default 10,
  health text not null default 'ok',
  last_crawl_at timestamptz
);

create table if not exists page_cache (
  url text primary key,
  site_id int references tracked_site(id) on delete cascade,
  status int,
  etag text,
  content_hash text,
  is_book boolean,
  fetched_at timestamptz not null default now()
);

create table if not exists work (
  id bigserial primary key,
  key text unique not null,
  title text not null,
  authors text[] not null default '{}',
  language text,
  year int,
  pages int,
  description text,
  embedding vector(768),
  first_seen timestamptz not null default now()
);

create table if not exists edition (
  id bigserial primary key,
  work_id bigint not null references work(id) on delete cascade,
  site_id int references tracked_site(id) on delete set null,
  url text unique not null,
  isbn13 text,
  language text,
  price numeric,
  currency text,
  rating real,
  rating_count int,
  published date,
  fetched_at timestamptz not null default now()
);

create table if not exists review_page (
  url text primary key,
  site_id int references tracked_site(id) on delete cascade,
  headline text not null,
  description text,
  published date,
  fetched_at timestamptz not null default now()
);

create table if not exists evidence (
  id bigserial primary key,
  work_id bigint not null references work(id) on delete cascade,
  kind text not null check (kind in ('rating', 'review', 'publisher')),
  source_name text not null,
  url text not null,
  rating real,
  rating_count int,
  excerpt text,
  fetched_at timestamptz not null default now(),
  unique (work_id, kind, url)
);
-- migration for databases created before evidence was unique per kind
alter table evidence drop constraint if exists evidence_work_id_url_key;
create unique index if not exists evidence_work_id_kind_url_key on evidence (work_id, kind, url);

create table if not exists candidate (
  run_date date not null,
  work_id bigint not null references work(id) on delete cascade,
  facet_slug text not null,
  score real not null,
  parts jsonb not null,
  rank int not null,
  primary key (run_date, work_id)
);

create table if not exists recommendation (
  id serial primary key,
  date date unique not null,
  work_id bigint not null references work(id),
  facet_slug text not null,
  exploration boolean not null default false,
  status text not null default 'ready' check (status in ('ready', 'held', 'published', 'skipped')),
  judge jsonb,
  digest jsonb not null,
  why text not null,
  runner_ups bigint[] not null default '{}',
  page_path text,
  created_at timestamptz not null default now(),
  published_at timestamptz
);

create table if not exists reaction (
  id bigserial primary key,
  rec_id int not null references recommendation(id) on delete cascade,
  kind text not null check (kind in ('want', 'not', 'finished', 'comment')),
  comment text,
  parsed jsonb,
  at timestamptz not null default now()
);

create table if not exists visitor_reaction (
  id bigserial primary key,
  rec_id int not null references recommendation(id) on delete cascade,
  kind text not null,
  at timestamptz not null default now()
);

create table if not exists reward (
  rec_id int primary key references recommendation(id) on delete cascade,
  value real not null,
  parts jsonb not null,
  updated_at timestamptz not null default now()
);

create table if not exists bandit_state (
  facet_slug text primary key,
  alpha real not null,
  beta real not null,
  updated_at timestamptz not null default now()
);

create table if not exists proposal (
  id serial primary key,
  kind text not null check (kind in ('taste_text', 'taste_change', 'profile')),
  payload jsonb not null,
  reason text,
  status text not null default 'pending' check (status in ('pending', 'approved', 'rejected', 'parsed')),
  created_at timestamptz not null default now(),
  decided_at timestamptz
);

create table if not exists llm_call (
  id bigserial primary key,
  task text not null,
  provider text not null,
  model text not null,
  ok boolean not null,
  shadow boolean not null default false,
  input_tokens int,
  output_tokens int,
  cost_usd numeric not null default 0,
  latency_ms int,
  error text,
  output jsonb,
  at timestamptz not null default now()
);

create table if not exists run_log (
  id bigserial primary key,
  command text not null,
  stage text not null,
  status text not null,
  detail jsonb not null default '{}',
  at timestamptz not null default now()
);

-- Close every table to the public API.
do $$ declare t text; begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on public.%I from anon, authenticated', t);
  end loop;
end $$;

-- ---------- functions the console and the daily pages call ----------

create or replace function alx_is_owner(p_key text) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from app_owner
                 where key_hash = encode(sha256(convert_to(coalesce(p_key, ''), 'UTF8')), 'hex'));
$$;

create or replace function alx_require_owner(p_key text) returns void
language plpgsql stable security definer set search_path = public as $$
begin
  if not alx_is_owner(p_key) then raise exception 'not the owner' using errcode = '42501'; end if;
end $$;

create or replace function alx_console_state(p_key text) returns jsonb
language plpgsql stable security definer set search_path = public as $$
begin
  perform alx_require_owner(p_key);
  return jsonb_build_object(
    'facets', (select coalesce(jsonb_agg(jsonb_build_object('slug', slug, 'name', name, 'priority', priority,
                 'keywords', keywords, 'status', status) order by priority desc, slug), '[]') from taste_facet where status <> 'removed'),
    'sites', (select coalesce(jsonb_agg(jsonb_build_object('name', name, 'url', url, 'kind', kind, 'mode', mode,
                 'mode_reason', mode_reason, 'health', health, 'last_crawl_at', last_crawl_at) order by name), '[]') from tracked_site),
    'proposals', (select coalesce(jsonb_agg(jsonb_build_object('id', id, 'kind', kind, 'payload', payload, 'reason', reason,
                 'created_at', created_at) order by id), '[]') from proposal where status = 'pending' and kind <> 'taste_text'),
    'picks', (select coalesce(jsonb_agg(p order by p->>'date' desc), '[]') from (
                 select jsonb_build_object('id', r.id, 'date', r.date, 'title', w.title, 'status', r.status, 'page', r.page_path,
                   'reactions', (select coalesce(jsonb_agg(x.kind order by x.at), '[]') from reaction x where x.rec_id = r.id)) p
                 from recommendation r join work w on w.id = r.work_id order by r.date desc limit 14) q),
    'paused', coalesce((select value from control where key = 'paused'), 'false'),
    'spend_7d', (select coalesce(round(sum(cost_usd), 4), 0) from llm_call where at > now() - interval '7 days'),
    'runs', (select coalesce(jsonb_agg(jsonb_build_object('at', at, 'command', command, 'stage', stage, 'status', status,
                 'detail', detail) order by at desc), '[]') from (select * from run_log order by at desc limit 8) l)
  );
end $$;

create or replace function alx_set_facet(p_key text, p_slug text, p_name text, p_priority real,
                                         p_keywords text[], p_status text) returns void
language plpgsql security definer set search_path = public as $$
declare existed boolean;
begin
  perform alx_require_owner(p_key);
  select exists (select 1 from taste_facet where slug = p_slug) into existed;
  insert into taste_facet (slug, name, priority, keywords, status)
  values (p_slug, p_name, p_priority, coalesce(p_keywords, '{}'), coalesce(p_status, 'active'))
  on conflict (slug) do update set name = excluded.name, priority = excluded.priority,
    keywords = excluded.keywords, status = excluded.status;
  insert into taste_event (facet_slug, kind, payload, source)
  values (p_slug, case when not existed then 'add' when p_status = 'paused' then 'pause'
                       when p_status = 'removed' then 'remove' else 'reweight' end,
          jsonb_build_object('name', p_name, 'priority', p_priority, 'keywords', p_keywords, 'status', p_status), 'console');
end $$;

create or replace function alx_note_taste(p_key text, p_text text) returns void
language plpgsql security definer set search_path = public as $$
begin
  perform alx_require_owner(p_key);
  insert into proposal (kind, payload, reason) values ('taste_text', jsonb_build_object('text', left(p_text, 2000)), 'console note');
end $$;

create or replace function alx_add_site(p_key text, p_name text, p_url text, p_kind text, p_language text,
                                        p_watch text[], p_link_pattern text, p_search_template text) returns void
language plpgsql security definer set search_path = public as $$
begin
  perform alx_require_owner(p_key);
  insert into tracked_site (name, url, kind, language, watch, link_pattern, search_template, mode)
  values (p_name, rtrim(p_url, '/'), p_kind, coalesce(p_language, 'en'), coalesce(p_watch, '{}'), p_link_pattern, p_search_template, 'pending')
  on conflict (url) do update set name = excluded.name, kind = excluded.kind, language = excluded.language,
    watch = excluded.watch, link_pattern = excluded.link_pattern, search_template = excluded.search_template, mode = 'pending';
end $$;

create or replace function alx_remove_site(p_key text, p_url text) returns void
language plpgsql security definer set search_path = public as $$
begin
  perform alx_require_owner(p_key);
  delete from tracked_site where url = rtrim(p_url, '/');
end $$;

create or replace function alx_decide_proposal(p_key text, p_id int, p_approve boolean) returns void
language plpgsql security definer set search_path = public as $$
declare p proposal;
begin
  perform alx_require_owner(p_key);
  select * into p from proposal where id = p_id and status = 'pending' for update;
  if not found then raise exception 'no pending proposal %', p_id; end if;
  if p_approve and p.kind = 'taste_change' then
    insert into taste_facet (slug, name, priority, keywords, status)
    values (p.payload->>'slug', p.payload->>'name', (p.payload->>'priority')::real,
            array(select jsonb_array_elements_text(coalesce(p.payload->'keywords', '[]'))), coalesce(p.payload->>'status', 'active'))
    on conflict (slug) do update set name = excluded.name, priority = excluded.priority,
      keywords = case when cardinality(excluded.keywords) > 0 then excluded.keywords else taste_facet.keywords end,
      status = excluded.status;
    insert into taste_event (facet_slug, kind, payload, source) values (p.payload->>'slug', 'reweight', p.payload, 'reflection');
  elsif p_approve and p.kind = 'profile' then
    insert into profile_version (text, facets, approved_at)
    values (p.payload->>'text', (select coalesce(jsonb_agg(to_jsonb(f)), '[]') from taste_facet f where status = 'active'), now());
  end if;
  update proposal set status = case when p_approve then 'approved' else 'rejected' end, decided_at = now() where id = p_id;
end $$;

create or replace function alx_react(p_key text, p_rec_id int, p_kind text, p_comment text) returns text
language plpgsql security definer set search_path = public as $$
begin
  if p_kind not in ('want', 'not', 'finished', 'comment') then raise exception 'unknown reaction %', p_kind; end if;
  if alx_is_owner(p_key) then
    insert into reaction (rec_id, kind, comment) values (p_rec_id, p_kind, left(p_comment, 2000));
    return 'owner';
  end if;
  if p_kind <> 'comment' then
    insert into visitor_reaction (rec_id, kind) values (p_rec_id, p_kind);
  end if;
  return 'visitor';
end $$;

create or replace function alx_set_pick_status(p_key text, p_date date, p_status text) returns void
language plpgsql security definer set search_path = public as $$
begin
  perform alx_require_owner(p_key);
  if p_status not in ('ready', 'held', 'skipped') then raise exception 'bad status %', p_status; end if;
  update recommendation set status = p_status where date = p_date and status <> 'published';
end $$;

create or replace function alx_set_paused(p_key text, p_paused boolean) returns void
language plpgsql security definer set search_path = public as $$
begin
  perform alx_require_owner(p_key);
  insert into control (key, value) values ('paused', p_paused::text)
  on conflict (key) do update set value = excluded.value;
end $$;

revoke all on function alx_is_owner(text), alx_require_owner(text) from public, anon, authenticated;
grant execute on function alx_console_state(text), alx_set_facet(text, text, text, real, text[], text),
  alx_note_taste(text, text), alx_add_site(text, text, text, text, text, text[], text, text), alx_remove_site(text, text),
  alx_decide_proposal(text, int, boolean), alx_react(text, int, text, text), alx_set_pick_status(text, date, text),
  alx_set_paused(text, boolean) to anon, authenticated;
