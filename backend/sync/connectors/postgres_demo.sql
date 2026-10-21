-- A stand-in for a legacy system, for the local demo of the postgres connector.
-- Apply to local Supabase:  docker exec -i supabase_db_social-media-campaigns psql -U postgres -d postgres < backend/sync/connectors/postgres_demo.sql
-- Then register the connector (config without secrets) and point SYNC_POSTGRES_DSN at the database:
--   insert into public.sync_connectors (name, schedule_cron, enabled, config) values ('postgres', '*/15 * * * *', true,
--     '{"table": "legacy.contacts", "default_region": "PL", "attributes": ["segment"], "columns": {"external_ref": "id", "locale": null}}');
create schema if not exists legacy;
create table if not exists legacy.contacts (
  id          serial primary key,
  phone       text not null,
  first_name  text,
  country     text,
  segment     text,
  consent     text check (consent in ('opted_in', 'opted_out')),
  updated_at  timestamptz not null default now()
);
insert into legacy.contacts (phone, first_name, country, segment, consent, updated_at) values
  ('+48 600 100 001', 'Jan',    'PL', 'donors',     'opted_in',  '2026-10-10 10:00+00'),
  ('600 100 002',     'Anna',   'PL', 'volunteers', 'opted_in',  '2026-10-11 10:00+00'),
  ('+49 1512 3456789','Klaus',  'DE', 'donors',     'opted_out', '2026-10-12 10:00+00'),
  ('nope',            'Broken', 'PL', 'donors',     'opted_in',  '2026-10-13 10:00+00')
on conflict do nothing;
