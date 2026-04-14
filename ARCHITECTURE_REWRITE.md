# Architecture Rewrite

This branch now runs around a split application shape instead of the old monolith web shell.

## Current runtime shape

- **Backend**: FastAPI API service at `backend/app/main.py`
- **Frontend**: SPA at `frontend/src/main.tsx`
- **Business layer**: backend-native workflow, skills, semantic, execution, and config modules under `backend/app`

The old root-level template/static web shell is no longer the active application architecture on this branch.

## Why rewrite

The legacy app accumulated product capabilities, but execution lifecycle, message state, UI state, and thread history became too tightly coupled. This rewrite separates those concerns so that:

- backend execution can model runs explicitly
- frontend state can reflect real run progress
- messages become outputs of runs rather than the run itself
- admin/audit capabilities stay part of the product instead of being bolted on

## Target architecture

### Backend domain model
The rewrite backend treats these as first-class persisted objects:

- `Thread`
- `Turn`
- `Run`
- `Message`
- `AuditLog`

### Frontend model
The SPA consumes backend thread detail and derives UI state from:

- active thread
- active run
- run steps
- latest assistant messages
- admin/profile state

## Design principles

1. `Run` is a first-class object.
   - stop = cancel run
   - regenerate = create a new run for an existing turn
   - progress = queryable run state
2. Assistant messages are outputs of runs, not the run itself.
3. Threads, turns, runs, and messages should be independently queryable.
4. Admin and audit capabilities remain part of the product, not bolt-ons.
5. `backend/app/config/tables.json` is the schema registry source of truth.
6. The active backend should not depend on a parallel legacy business tree.

## Current architecture map

### Backend
- `backend/app/main.py`
  - FastAPI entrypoint
- `backend/app/api/routes.py`
  - auth, thread, run, admin, audit routes
- `backend/app/services/*`
  - run lifecycle, thread queries, auth/admin orchestration
- `backend/app/models/*`
  - rewrite persistence model
- `backend/app/workflow/*`
  - orchestration, routing, history shaping
- `backend/app/semantic/*`
  - filter extraction, heuristics, domain mapping
- `backend/app/execution/*`
  - LLM, SQL hardening/lint, SQL execution
- `backend/app/config/*`
  - schema and routing config

### Frontend
- `frontend/src/main.tsx`
  - SPA mount point
- `frontend/src/App.tsx`
  - top-level app container
- `frontend/src/api.ts`
  - backend API client helpers
- `frontend/src/components.tsx`
  - thread/run/admin/profile/message UI components
- `frontend/src/view-models.ts`
  - derived run/message state

## Current rewrite status

Implemented:

- split backend/frontend structure
- rewrite backend entrypoint and API routes
- persisted `Thread / Turn / Run / Message / AuditLog` model
- auth, admin, audit APIs
- run lifecycle with `pending / running / cancelling / completed / failed / cancelled`
- send / regenerate / cancel APIs aligned to run objects
- SPA login/register/chat/profile/admin/audit pages
- polling-based run progress UI
- SQL details and result-table rendering in the SPA
- backend-native workflow/semantic/execution/config stack
- removal of the legacy template/static shell from the active architecture
- removal of the legacy business tree from active runtime ownership

Still evolving:

- thinner frontend container layer
- richer progress behavior beyond polling
- more focused prompt/routing tuning against production data

## Execution lifecycle

Current request flow is:

1. frontend sends a question to the rewrite API
2. backend creates `Turn` + `Run`
3. background execution advances the run through route/workflow/answer stages
4. frontend polls thread detail while a run is active
5. final assistant message is written only when the run completes successfully
6. cancel/regenerate operate on runs rather than on the page shell

## Development topology

### Run backend
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Run frontend
```bash
cd frontend
npm install
npm run dev
```

The Vite frontend proxies `/api` to the backend on port `8000`.

## Verification expectations

A rewrite change should verify at least:

- backend import/startup works
- `/api/health` responds
- frontend builds successfully
- send / regenerate / cancel flows reach terminal run states
- admin data still works, including `last_login_at`

## Key preserved asset

- `backend/app/config/tables.json`
  - schema registry source of truth for the active backend
