# Frontend Rewrite

This directory contains the new SPA frontend for the architecture rewrite.

## Goals
- replace the legacy template + hand-written DOM approach
- consume the new backend API directly
- make chat, thread, run, and admin states explicit and maintainable
- support richer run-aware UX for progress, regenerate, stop, SQL details, and table results

## Current structure
- `src/api.ts` — backend API client helpers
- `src/App.tsx` — current top-level container
- `src/components.tsx` — shared UI components
- `src/view-models.ts` — derived state helpers
- `src/styles.css` — rewrite UI styles

## Planned capabilities
- auth flows
- chat workspace
- thread list
- run progress panel
- message actions
- SQL details
- admin pages
- audit view

## Run locally
```bash
cd frontend
npm install
npm run dev
```

## Current status
The rewrite frontend already supports login/register, threads, basic chat, regenerate, stop, SQL details, profile, admin users, and audit pages. It is still being modularized so `App.tsx` becomes thinner over time.
