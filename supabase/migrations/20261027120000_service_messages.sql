-- Service messages (plain text inside Meta's 24-hour window) live next to template messages.
alter table public.messages alter column template_id drop not null;
alter table public.messages add column kind text not null default 'template'
  check (kind in ('template', 'text'));
alter table public.messages add column text text;
alter table public.messages drop constraint messages_status_check;
alter table public.messages add constraint messages_status_check
  check (status in ('pending', 'sent', 'delivered', 'read', 'failed', 'skipped'));
