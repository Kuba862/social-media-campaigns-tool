-- Saved service messages live next to Meta templates: kind tells them apart, READY is their status.
alter table public.templates add column kind text not null default 'template'
  check (kind in ('template', 'service'));
alter table public.templates drop constraint templates_status_check;
alter table public.templates add constraint templates_status_check check (
  status in (
    'DRAFT', 'READY', 'APPROVED', 'IN_APPEAL', 'PENDING', 'REJECTED', 'PENDING_DELETION',
    'DELETED', 'DISABLED', 'PAUSED', 'LIMIT_EXCEEDED', 'ARCHIVED'
  )
);
