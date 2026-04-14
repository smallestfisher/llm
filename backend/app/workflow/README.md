# Workflow Layer

This layer now owns the rewritten routing, orchestration, cross-domain
composition, chat-history shaping, and workflow execution entrypoints.

It still uses `core/config/tables.json` as the schema source of truth, while the
runtime logic itself lives under `backend/app`.
