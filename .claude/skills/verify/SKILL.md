---
name: verify
description: How to run and observe Recitroc end-to-end (API + browser) to verify changes.
---

# Verifying Recitroc changes

The whole stack runs under docker compose (`make dev`); nginx-proxy exposes it at
`http://recitroc.localhost/` (frontend) and `http://recitroc.localhost/api` (backend).
Verify at those surfaces — don't import app modules directly.

## Backend / API surface

- Base URL: `http://recitroc.localhost/api/v1`.
- Auth: `POST /auth/signup` (JSON), then `POST /auth/login` with **form** fields
  `username=<email>&password=...` → `access_token`; pass as `Authorization: Bearer`.
- Most flows need a location first: `PUT /users/me/location {"city": "Berlin"}`
  (geocoded server-side; needs outbound network from the backend container).
- Use timestamped emails (`ada.$(date +%s)@test.dev`) — email is the users PK and
  dev postgres data persists across runs.
- New migrations are only applied at container start; after adding one, run
  `make migrate`. Check state with `docker compose exec backend alembic current`.

## Frontend / browser surface

No playwright installed, but host has `google-chrome` and python `websockets`:
drive headless Chrome over CDP (`--headless=new --remote-debugging-port=<port>
--no-sandbox --user-data-dir=<scratch>`), fetch the page's
`webSocketDebuggerUrl` from `http://localhost:<port>/json`, then
`Page.navigate` / `Runtime.evaluate` / `Page.captureScreenshot`.

- Log in by injecting the token the app itself stores:
  `localStorage.setItem('recitroc_token', <token>)` on the recitroc.localhost
  origin, then reload.
- Vite hot-reloads mounted `frontend/src`; no rebuild needed for src changes.
- Typecheck (not verification, but cheap): `docker compose exec -T frontend npx tsc --noEmit`.

## Gotchas

- `make test` runs backend pytest against in-memory SQLite — it is CI, not verification.
- Backend hot reload covers `backend/app`; config/env changes need `make dev` again.
