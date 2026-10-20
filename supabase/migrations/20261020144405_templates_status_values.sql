-- Templates carry any status Meta reports, plus our local DRAFT before submission.
alter table public.templates drop constraint templates_status_check;
alter table public.templates add constraint templates_status_check check (
  status in (
    'DRAFT', 'APPROVED', 'IN_APPEAL', 'PENDING', 'REJECTED', 'PENDING_DELETION',
    'DELETED', 'DISABLED', 'PAUSED', 'LIMIT_EXCEEDED', 'ARCHIVED'
  )
);
