# Progress

Updated at the end of every part. Stable rules live in `CLAUDE.md`; this file is the current state.

## Now: Phase 1 (Walking skeleton), Part 3 of 6 is next

### Approved plan for Phase 1
1. [x] **Repo skeleton + infra.** Folder layout, `.gitignore`, `.env.example`, Docker Compose with
   Postgres 16 + pgvector (host port 5433) and Redis 7, both with healthchecks. Init script enables
   `vector` and `pg_trgm`.
2. [x] **Backend skeleton.** uv project on Python 3.12, typed settings (`pydantic-settings`), async
   SQLAlchemy engine + redis client owned by the app lifespan, `/health/live` (liveness) and `/health`
   (readiness: concurrent probes, 1s timeout, 503 + per-component status when degraded). Tests pass.
3. [ ] **Event contract + SSE.** Pydantic event schema in `backend/app/events/schema.py` with contract
   tests; publisher on Redis channel `events:{run_id}`; fake run generator walking 2,000 items through
   `queued → parsing → chunking → embedding → indexed | failed`; `GET /runs/{id}/events` relaying
   Redis pub/sub to the browser over SSE. *Check:* `curl.exe -N` shows events streaming.
4. [ ] **Frontend shell.** `create-next-app` (TypeScript, Tailwind, App Router), design tokens from
   CLAUDE.md, routes `/`, `/query`, `/evals`, `/system`, and `frontend/lib/events.ts` mirroring the schema.
5. [ ] **Canvas grid.** Pure event reducer (`state + event → state`) with a unit test, `<canvas>`
   renderer redrawing only changed cells, `EventSource` hook, "Start fake run" button.
   *Phase 1 done when:* the grid animates from the fake event stream.
6. [ ] **Docs.** README (setup, full command reference, demo steps), ADRs for the decisions below,
   recap.

## Decisions made (write as ADRs in Part 6)
- **SSE, not WebSockets.** Data flows server → browser only; SSE auto-reconnects and is plain HTTP.
  Hand-written SSE endpoint; no `sse-starlette` dependency.
- **Fake events go through Redis pub/sub.** The API never generates events itself, so Phase 2's real
  workers replace the fake generator without UI changes.
- **asyncpg, not psycopg 3.** asyncpg runs on Windows' default Proactor event loop; psycopg async needs
  the Selector loop.
- **Liveness vs readiness split.** `/health/live` never touches dependencies; `/health` does.
- **No arq until Phase 2.** The fake generator runs as a plain background task.

## Gotchas
- Native Windows Postgres holds port 5432. Container is on **5433**; a `password authentication failed`
  error almost always means something hit 5432.
- Shell is Windows PowerShell 5.1: `curl` is an alias for `Invoke-WebRequest`; use `curl.exe`.
- Starlette 1.7 deprecates `httpx` for `TestClient`; the dev dependency is **`httpx2`**.
- VS Code's Python interpreter must be `backend\.venv\Scripts\python.exe` (system Python is 3.11).

## Useful commands (move to README in Part 6)
```
docker compose ps                                  # both must read "running (healthy)"
docker compose down -v                             # stop and DESTROY all data (full reset)
docker compose exec postgres psql -U recall -d recall
docker compose exec redis redis-cli
uv sync                                            # from backend/: install deps from uv.lock
curl.exe -s http://localhost:8000/health           # readiness; 503 if a dependency is down
uv run ruff check .                                # from backend/: lint (add --fix for imports)
```
