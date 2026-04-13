# Architecture Rewrite

This branch contains the in-progress rewrite of the BOE Data Copilot application.

## Why rewrite
The legacy app successfully accumulated product capabilities, but execution lifecycle, message state, UI state, and thread history became too tightly coupled. This rewrite aims to separate concerns instead of layering more patch fixes onto the legacy stack.

## Target architecture
- **Backend**: FastAPI API service
- **Frontend**: SPA
- **Shared domain model**:
  - `Thread`
  - `Turn`
  - `Run`
  - `Message`
  - `AuditLog`

## Design principles
1. `Run` is a first-class object.
   - stop = cancel run
   - regenerate = create a new run for a turn
   - progress = active run state
2. Assistant messages are outputs of runs, not the run itself.
3. Threads, turns, runs, and messages should be independently queryable.
4. Admin and audit capabilities remain part of the product, not bolt-ons.
5. `core/config/tables.json` remains the schema registry source of truth.

## Current migration approach
- Build the new backend and frontend in parallel.
- Preserve business semantics from the existing router/workflow/SQL safety stack.
- Initially bridge to existing core workflow modules where needed.
- Gradually replace bridge-style execution with native rewrite lifecycle handling.

## Current rewrite status
Implemented or in progress:
- separated backend/frontend structure
- auth and session flows
- thread / turn / run / message models
- admin and audit APIs
- basic SPA workspace
- run-aware UI panels
- workflow bridge into existing execution logic

Still evolving:
- deeper native run lifecycle
- less bridge dependence on legacy execution modules
- thinner frontend container layer
- more complete streaming/progress behavior

## Key preserved asset
- `core/config/tables.json`
