-- Leads from the landing-page form, scored by the logistic-regression model (ADR-0005).
-- Only the backend inserts (service role, which bypasses RLS). The admin reads and updates status.
-- Check constraints mirror backend/app/schemas/leads.py. event_date "in the future" is validated
-- in Pydantic only: a check constraint cannot use now().

create type lead_status as enum ('new', 'contacted', 'quoted', 'won', 'lost');

create table leads (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  full_name text not null check (char_length(full_name) between 2 and 80),
  phone text not null check (phone ~ '^0(5[0-9]|[2-489])[0-9]{7}$'),
  email text check (email is null or (char_length(email) <= 254 and email ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$')),
  event_type text not null check (event_type in
    ('יום הולדת', 'אירוע משפחתי', 'בר או בת מצווה', 'ארוחת שבת', 'יום נישואין', 'חגיגה פרטית', 'אחר')),
  event_date date not null,
  guests int not null check (guests between 1 and 5000),
  budget_band text not null check (budget_band in ('low', 'mid', 'high', 'premium')),
  source text check (source is null or char_length(source) <= 100),
  message text check (message is null or char_length(message) <= 1000),
  consent boolean not null check (consent),
  status lead_status not null default 'new',
  score numeric(5, 4) check (score is null or score between 0 and 1),
  score_model_version text,
  score_reasons jsonb,
  customer_id uuid references customers (id) on delete set null
);

create index leads_score_idx on leads (score desc);

alter table leads enable row level security;

-- New tables get default grants for anon and authenticated in Supabase. Remove them, then grant the minimum.
revoke all on leads from anon, authenticated;
grant select on leads to authenticated;
grant update (status, customer_id) on leads to authenticated;

create policy "admin reads" on leads for select to authenticated
  using ((select private.is_admin()));
create policy "admin updates" on leads for update to authenticated
  using ((select private.is_admin())) with check ((select private.is_admin()));
