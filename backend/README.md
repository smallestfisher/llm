# Backend Rewrite

This directory contains the FastAPI backend for BOE Data Copilot.

## Role in the system

The backend is the canonical server-side entrypoint for the application.

It is responsible for:

- auth APIs
- thread / turn / run / message APIs
- run cancellation and regeneration
- admin and audit APIs
- persisting backend-side state
- executing routing, orchestration, SQL hardening, SQL execution, and answer generation inside `backend/app`

## Current structure

- `app/main.py` — FastAPI entrypoint
- `app/api` — HTTP routes
- `app/models` — ORM models
- `app/repositories` — persistence helpers
- `app/schemas` — request/response contracts
- `app/services` — application services
- `app/workflow` — routing, orchestration, history shaping
- `app/semantic` — heuristics, filters, domain mapping
- `app/execution` — LLM, SQL guard, SQL executor
- `app/config` — schema and routing config
- `app/presentation` — final answer payload shaping

## Runtime model

The backend treats these as first-class objects:

- `Thread`
- `Turn`
- `Run`
- `Message`
- `AuditLog`

A message send or regenerate request starts a `Run` instead of waiting synchronously for a final answer.

## Current run lifecycle

A run can move through:

- `pending`
- `running`
- `cancelling`
- `completed`
- `failed`
- `cancelled`

Current execution stages exposed to the frontend are:

- `route`
- `workflow`
- `answer`

## Run locally

```bash
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Environment

The backend uses `BACKEND_DB_URI` for its local persistence store.

Example:

```env
BACKEND_DB_URI=sqlite:////absolute/path/to/backend/app_rewrite.db
```

If unset, the backend falls back to the rewrite-local SQLite file under `backend/`.

## Verification

Recommended checks for backend changes:

```bash
python3 -m compileall backend/app
curl http://127.0.0.1:8000/api/health
```

And for behavioral verification:

- register / login
- create thread
- send message
- regenerate response
- cancel running run
- verify admin users and audit APIs

## Current status

The backend is functional and drives the rewrite UI end to end without relying on a parallel legacy business tree.
