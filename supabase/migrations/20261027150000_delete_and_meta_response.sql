-- Deleting a template keeps the log: messages.template_id becomes null. Every sent message keeps
-- Meta's whole send response for the log's detail view.
alter table public.messages drop constraint messages_template_id_fkey;
alter table public.messages add constraint messages_template_id_fkey
  foreign key (template_id) references public.templates (id) on delete set null;
alter table public.messages add column meta_response jsonb;
