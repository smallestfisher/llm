# Backend Rewrite

This directory contains the new FastAPI backend for the architecture rewrite.

## Goals
- separate API backend from frontend SPA
- preserve all product capabilities from the legacy app
- make Thread / Turn / Run / Message first-class domain objects
- keep `core/config/tables.json` as the schema registry source of truth

## Current structure
- `app/api` — HTTP routes
- `app/domain` — core business objects and enums
- `app/models` — ORM models
- `app/repositories` — persistence helpers
- `app/schemas` — request/response contracts
- `app/services` — application services
- `app/workflow` — routing, execution, SQL/runtime bridges
- `app/config` — config and schema registry

## Run locally
```bash
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

## Current status
The rewrite is in progress. Core API, auth, thread/run models, admin routes, and the first workflow bridge are already present. Some execution still delegates into existing core workflow modules while the new backend lifecycle is being stabilized.
