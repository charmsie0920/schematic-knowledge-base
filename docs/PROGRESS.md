# docs/PROGRESS.md
# Progress

Updated at the end of every part. Stable rules live in `CLAUDE.md`; this file is the current state.

## Now: Phase 1 (Walking skeleton), Part 4 of 6 is next

### Approved plan for Phase 1
1. [x] **Repo skeleton + infra.** Folder layout, `.gitignore`, `.env.example`, Docker Compose with
   Postgres 16 + pgvector (host port 5433) and Redis 7, both with healthchecks. Init script enables
   `vector` and `pg_trgm`.
2. [x] **Backend skeleton.** uv project on Python 3.12, typed settings (`pydantic-settings`), async
   SQLAlchemy engine + redis client owned by the app lifespan, `/health/live` (liveness) and `/health`
   (readiness: concurrent probes, 1s timeout, 503 + per-component status when degraded). Tests pass.
3. [x] **Event contract + SSE.** Pydantic event schema (`RunStarted`, `ItemStateChanged`, `RunDone`,
   discriminated on `type`) with contract tests and a transition checker; Redis publisher (pipelined
   bursts) on `events:{run_id}`; seeded fake run (2,000 items, 64 workers, ~3% failures, ~20s);
   `POST /runs/fake` (202 + `events_url`) and `GET /runs/{id}/events` relaying pub/sub over SSE with
   15s heartbeats. 44 tests pass. *Checked:* `curl.exe -N` streams ~9,940 events and closes on `run.done`.
4. [ ] **Frontend shell.** `create-next-app` (TypeScript, Tailwind, App Router), design tokens from
   CLAUDE.md, routes `/`, `/query`, `/evals`, `/system`, and `frontend/lib/events.ts` mirroring the schema
   (including `run.started` / `run.done`).
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
- **Run-level events added to the contract.** `run.started` carries `total_items` (the grid sizes
  itself up front); `run.done` carries counts and duration and tells the server to close the stream.
- **Discriminated union on `type`, frozen models, `extra="forbid"`.** One precise error per bad event;
  typos fail loudly. The relay validates every message and drops (logs) invalid ones.
- **Unnamed SSE messages.** Everything arrives in `onmessage`; the reducer switches on `type`.
- **Run waits for its first subscriber** (polls `PUBSUB NUMSUB`, 30s cap) because pub/sub drops messages
  with no listener. Replaced by persisted events + replay in Phase 2.
- **`TaskRegistry` instead of bare `create_task` or FastAPI `BackgroundTasks`.** Holds strong refs (no
  GC mid-run), logs failures, cancels on shutdown. `BackgroundTasks` can't be cancelled, and blocks
  TestClient responses.
- **Seeded fake runs plan all randomness up front**, so a seed is reproducible under concurrency.
- **No `pytest-asyncio`.** Async code is tested with `asyncio.run()` inside sync tests.
- **`anyio` declared as a direct dependency** (already present via Starlette) because the relay imports
  `anyio.CancelScope` to shield cleanup on disconnect.

## Gotchas
- Native Windows Postgres holds port 5432. Container is on **5433**; a `password authentication failed`
  error almost always means something hit 5432.
- Shell is Windows PowerShell 5.1: `curl` is an alias for `Invoke-WebRequest`; use `curl.exe`. For JSON
  bodies use `Invoke-RestMethod -Body '{...}'`; quoting JSON for `curl.exe -d` in PS 5.1 is painful.
- Starlette 1.7 deprecates `httpx` for `TestClient`; the dev dependency is **`httpx2`**.
- VS Code's Python interpreter must be `backend\.venv\Scripts\python.exe` (system Python is 3.11).
- Redis pub/sub is fire-and-forget: anything published before a subscriber exists is lost.
- `EventSource` auto-reconnects when the server closes the stream. Part 5's hook **must call
  `close()` on `run.done`**, or the browser reconnects to a finished run and gets only heartbeats.
- Until Phase 2 persists runs, `GET /runs/{unknown}/events` returns 200 and just sends heartbeats forever.
- Without `anyio.CancelScope(shield=True)`, cleanup awaits in a cancelled SSE generator are cancelled too
  and the Redis connection leaks.

## Useful commands (move to README in Part 6)
