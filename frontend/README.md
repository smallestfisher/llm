# Frontend Rewrite

This directory contains the SPA frontend for the BOE Data Copilot rewrite.

## Role in the system

The frontend replaces the old server-rendered template/static shell.

It is responsible for:

- auth flows
- thread navigation
- chat workspace
- run progress presentation
- regenerate / cancel interactions
- SQL detail display
- profile page
- admin users page
- audit page

## Current structure

- `src/main.tsx` — SPA mount point
- `src/App.tsx` — top-level container
- `src/api.ts` — backend API client helpers
- `src/components.tsx` — shared UI components
- `src/view-models.ts` — derived state helpers
- `src/styles.css` — rewrite UI styles

## UI state model

The frontend derives most behavior from thread detail returned by the backend:

- active thread
- active run
- run steps
- latest assistant messages
- admin/profile state

That allows the UI to reflect real run lifecycle instead of assuming a single blocking request-response cycle.

## Current run behavior

After send or regenerate:

1. the SPA calls the rewrite API
2. the backend returns run-start information
3. the SPA refreshes thread detail
4. polling continues while the run is active
5. the UI reflects `pending / running / cancelling / completed / failed / cancelled`

The run panel and message actions are now driven by backend run state rather than legacy DOM event plumbing.

## Run locally

```bash
cd frontend
npm install
npm run dev
```

## Build

```bash
npm run build
```

## Dev proxy

`vite.config.ts` proxies `/api` to `http://127.0.0.1:8000`, so local development expects the rewrite backend to be running on that port.

## Current status

The frontend already supports login/register, threads, chat, regenerate, stop, SQL details, profile, admin users, and audit pages. It is still being refined structurally so `App.tsx` can get thinner over time, but it is already the active UI architecture for this branch.
