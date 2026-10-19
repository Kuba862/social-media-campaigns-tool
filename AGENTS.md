# AGENTS.md

Working rules for agents and humans contributing to this repository. The spec lives outside
the repo on the owner's machine, in `/Users/jakubrejch/Work/WhatsApp_v2/`:
`WhatsApp_V2_Brief_PoC.md` (what and why, wins on conflict) and
`WhatsApp_V2_Instrukcja_implementacji_dla_agentow_AI.md` (how). This file copies section 9
of the guide and adds what is specific to this repository.

## Working rules (guide, section 9)

- Branches: `feature/`, `fix/`, `chore/`, `docs/`. Commit messages follow Conventional Commits.
- One phase or sub-feature per PR, one step at a time. Keep PRs reviewable: target under
  600 changed lines, excluding generated files and lockfiles.
- PR description has five sections: Scope, Risk, Test evidence, Deployment, Rollback.
- Without explicit approval from the human owner do not: merge, deploy to production,
  change Vercel/GCP env, run destructive SQL, force-push.
- Do not add features outside the brief's scope. Note ideas in `docs/decisions.md` under "Later".
- Stop and ask when: Meta API behaviour contradicts the guide; a required credential is missing;
  a design choice affects consent, data retention or cost; tests cannot pass without weakening
  an acceptance check.
- Before claiming done: self-review the diff for debug code, secrets, unrelated changes and
  missing error handling at boundaries (Meta, Temporal, Supabase). Run the full test suite of
  every package you touched and report the tested commit SHA.

## This repository

Python packages live under `backend/` (guide section 2 puts them at the repo root); `web/`
will sit beside it. Everything else follows the guide. See `docs/decisions.md` for why.

```
AGENTS.md, CLAUDE.md      rules (this file; CLAUDE.md only points here)
docs/decisions.md         assumptions and decisions log, "Later" section for parked ideas
bin/                      gitignored local binaries, not on PATH: ./bin/supabase, ./bin/temporal,
                          ./bin/cloudflared (run them from the repo root)
backend/pyproject.toml    uv project "wa-backend", Python >= 3.12, ruff + mypy + pytest
backend/core/             pure Python, no I/O: journey_schema.py, validation.py, context.py
backend/api/              FastAPI app (empty package for now)
backend/worker/           Temporal worker, task queue "wa-journeys" (empty package for now)
backend/meta_client/      anti-corruption layer for the WhatsApp Cloud API (empty package for now)
backend/sync/             sync connectors, one module each (empty package for now)
backend/tests/            pytest: unit, workflow with time skipping, replay
web/                      Next.js panel (planned)
supabase/migrations/      SQL migrations, one per change (planned)
```

Rules specific to the code:

- `core/` must not import from `api/`, `worker/`, `meta_client/` or any SDK. Meta-specific
  payloads never leave `meta_client/`.
- Journey definitions follow guide section 4.1. Node types: start, send_template, wait,
  wait_for_reply, branch, update_contact, end. `wait_for_reply` has two outgoing edges with
  ports `replied` and `timeout`; `branch` has no edges, its targets are `conditions[].next`
  and `else`.
- mypy runs in strict mode for the whole backend. Ruff: line length 100, rules E, F, I, UP, B.
- Imports are rooted at `backend/` (`from core.journey_schema import ...`), so run every
  command from `backend/`.

Checks to run before claiming done:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```
