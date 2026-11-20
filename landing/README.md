# DebateSignal — Landing Page

Introductory and interactive exploration page for **DebateSignal**, a calm debate moderation workspace for two-person English debates.

## Running Locally

```bash
npm install
npm run dev
```

## Configuring `APP_URL`

All **Open workspace** links read from a single configuration module (`src/config.ts`).

To point the buttons to a deployed workspace instance, set `VITE_APP_URL` before building or running:

```bash
VITE_APP_URL="https://your-workspace-domain.example/" npm run build
```

When `VITE_APP_URL` is not set, `APP_URL` defaults to `/app/` on the same origin. The integrated FastAPI service serves this landing at `/`, sign-in at `/login`, account creation at `/signup`, and the protected workspace at `/app/`. Account forms call the real `/api/auth/*` endpoints; the former UI-only sign-in preview has been replaced.

For local Vite development, run the Python service on port 7863 first. The dev server proxies `/api` and `/app` to it. All account records and private debates use the existing `.local/sessions.sqlite3` database in the parent project. See the parent README for first-account setup, building both frontends and starting the integrated app.

## Production Build

```bash
npm run build
```
