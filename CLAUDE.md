# CLAUDE.md: Recall

> Personal knowledge engine. Hybrid RAG over my own notes and documents, with a live UI that visualizes every stage of the pipeline in real time.

## Why this project exists
This is a portfolio project. Its purpose is to demonstrate **system design and production AI engineering**, not language tricks. Every feature should make one of these visible:
1. Concurrency and streaming (live pipeline visualization)
2. Retrieval quality (hybrid search, reranking, measured by evals)
3. Production thinking (observability, cost, caching, failure handling)
4. Explainability (every answer traceable to its source passages)

When choosing between two approaches, prefer the one that is **easier to explain in a system design interview** and **measurable**.

## Architecture

```
 Sources (folder / upload / URL / Telegram capture)
        │
        ▼
 ┌──────────────┐   jobs    ┌──────────────────┐
 │  API (FastAPI)│ ────────▶│  Redis queue      │
 └──────┬───────┘           └────────┬─────────┘
        │ SSE                        ▼
        │               ┌──────────────────────────┐
        │               │ Worker pool (async)       │
        │               │ parse → chunk → embed →   │
        │               │ index                     │
        │               └────────┬─────────────────┘
        │   status events        │
        │◀── Redis pub/sub ◀─────┤
        ▼                        ▼
 ┌──────────────┐        ┌──────────────────────────┐
 │ Next.js UI   │        │ Postgres                  │
 │ live grid    │        │  - pgvector (embeddings)  │
 │ query view   │        │  - tsvector (BM25-style)  │
 │ evidence     │        │  - documents, chunks,     │
 │ evals        │        │    runs, events, evals    │
 └──────────────┘        └──────────────────────────┘
```

### Key design decisions (record new ones in `docs/decisions/`)
- **One database for vectors and keyword search** (Postgres + pgvector + tsvector). Fewer moving parts; hybrid search in one SQL query. Revisit only if evals or latency justify a dedicated vector DB.
- **Event-driven pipeline.** Workers never talk to the UI directly. Every state change is published as an event; the API relays events to the browser over SSE. The live grid is a pure consumer of this stream.
- **Idempotent ingestion.** Documents and chunks are keyed by content hash. Re-ingesting unchanged content is a no-op; changed files only re-embed changed chunks.
- **Provider abstraction.** LLM, embedding and reranker calls go through interfaces in `backend/app/providers/`, so hosted models and local models (Ollama) are swappable by config.
- **Every LLM call is traced**, with latency, tokens and cost recorded.

## Tech stack
- **Backend:** Python 3.12, FastAPI, async SQLAlchemy, Pydantic v2, arq (Redis-based async jobs)
- **Data:** Postgres with pgvector, Redis (queue + pub/sub + cache)
- **AI:** embedding model + cross-encoder reranker + LLM, all behind provider interfaces
- **Frontend:** Next.js (App Router), TypeScript, Tailwind, shadcn/ui, Framer Motion; the grid renders on `<canvas>` (must handle 5,000+ cells at 60fps)
- **Observability:** OpenTelemetry traces; per-request cost and latency stored in Postgres
- **Infra:** Docker Compose for local dev

Do not add new dependencies without stating why and what the alternative was.

## Repository layout
```
backend/
  app/
    api/          # FastAPI routes (ingest, query, events SSE, evals)
    pipeline/     # parse, chunk, embed, index stages
    retrieval/    # keyword search, vector search, fusion, rerank
    providers/    # LLM / embedding / reranker interfaces + implementations
    events/       # event schema + publisher
    models/       # SQLAlchemy models
    evals/        # eval runner + metrics
  tests/
frontend/
  app/            # routes: /, /query, /evals, /system
  components/
    grid/         # canvas grid + event reducer
    drawer/       # evidence drawer
    stats/        # bottom stats bar
docs/
  decisions/      # short ADRs: context, decision, alternatives, consequences
evals/
  datasets/       # question → expected source(s) → reference answer
docker-compose.yml
```

## Event contract (the backbone of the UI)
All events share this shape and are published on Redis channel `events:{run_id}`:
```json
{ "type": "item.state", "run_id": "…", "item_id": "…", "state": "embedding", "ts": 1727500000.123, "meta": {} }
```
Ingestion item states: `queued → parsing → chunking → embedding → indexed` or `failed`.

Query events, in order:
`query.started` → `query.rewritten` → `retrieval.keyword_hits` → `retrieval.vector_hits` → `retrieval.fused` → `rerank.scored` → `answer.token` (many) → `answer.citation` → `query.done` (includes latency breakdown, tokens, cost).

Rules:
- Events are append-only and also persisted, so any run can be **replayed** in the UI.
- Changing the contract means updating the schema in `backend/app/events/schema.py`, the TypeScript types in `frontend/lib/events.ts`, and this section.

## UI design system
- Dark background (`#0B0F0E`), panels slightly lighter (`#11171A`), hairline borders
- Accent: lime `#D4F45A` for "best / active"; teal `#3FB8A5` for "done"; orange `#E0955A` for "needs attention / failed"; muted slate for "waiting"
- Big confident numbers for metrics; small uppercase monospace labels with letter spacing
- Motion is meaningful: things move only when state changes
- Screens: **Ingest** (live grid + stats bar), **Query** (grid highlights hits, lines trace to Top sources panel, streamed answer with citations), **Evidence drawer** (scores, confidence, source passage), **Evals** (configs racing on the grid + leaderboard), **System** (latency, cost, cache hit rate over time)

## Build phases
Work one phase at a time. Each phase ends with passing tests, a short demo, and an updated README.

1. **Walking skeleton.** Docker Compose (Postgres + pgvector, Redis), FastAPI health route, Next.js shell, SSE endpoint streaming fake events to a canvas grid. *Done when:* the grid animates from a fake event stream.
2. **Real ingestion.** Folder/upload ingest, parse (md, txt, pdf), chunk, embed, index, content-hash idempotency, real events. *Done when:* ingesting 500+ docs fills the grid live and re-running is a no-op.
3. **Hybrid retrieval + answers.** Keyword + vector search, reciprocal rank fusion, streamed answer with citations, query mode in the UI.
4. **Reranker + evidence drawer.** Cross-encoder rerank, score breakdown per chunk, click-to-inspect.
5. **Evals.** Dataset of 50+ questions with expected sources; metrics: recall@k, MRR, answer faithfulness; compare configs; Evals screen.
6. **Production polish.** Tracing, cost tracking, semantic cache, retries with backoff, rate limiting, System screen.
7. **Demo mode + deploy.** Public sample corpus (my notes stay private), event replay, deploy, 60-second screen recording.
8. **Stretch:** MCP server exposing search/ask as tools; Telegram capture bot; local-only mode via Ollama.

## Working rules for Claude
- **Before starting any work, read `docs/PROGRESS.md`.** It holds the approved plan for the current phase and what's next. Continue from there; don't re-plan finished parts or reopen recorded decisions without saying why.
- Before writing code for a phase, propose a short plan and wait for approval.
- Keep functions small and typed. Pydantic models at every boundary.
- Write tests for pipeline stages, retrieval fusion, and the event contract.
- Never hardcode API keys; read from `.env` (keep `.env.example` updated).
- When making a non-obvious design choice, add an ADR in `docs/decisions/`.
- Prefer measuring over guessing: if a change claims to improve retrieval, run the evals and report numbers.

## Guidance mode (learning by building)
I am building this myself to learn. When I ask for **guidance** on a task or phase (e.g. "guide me through Phase 2", "how do I do X", "walk me through…"), follow these rules instead of editing files yourself:

1. **Do not write or modify files in the repo.** Give me the content so I can read it and type or paste it myself. Only edit files directly if I explicitly say "do it for me".
2. **Give exact, numbered steps in order.** Each step says what we're doing and why, in 1–2 sentences, before the code.
3. **Include every CLI command and setup step.** Installs, env vars, Docker commands, migrations, folder creation. Show the exact command in a code block, which directory to run it from, and what output to expect.
4. **Always give complete files, never snippets.** Every code block is the full file, from the first import to the last line, with its path as the first line of the block (e.g. `# backend/app/events/schema.py`). No `...`, no "rest unchanged", no "add this somewhere". If an existing file changes, give the whole updated file and briefly say what changed.
5. **Explain the code after each file.** A short walkthrough of the important parts: what each section does and why it's designed that way, especially the system design reasoning.
6. **End each step with a check.** A command to run or a thing to look at that proves the step worked, plus the most likely error and its fix.
7. **Finish with a recap.** What we built, how it fits the architecture diagram, and what I'd say about it in an interview.
8. **Suggest commit messages** Provide suggested commit messages for what we have done iteratively, to adhere good commit and development practice. 
9. **Update progress.** At the end of each part, give the updated `docs/PROGRESS.md` (tick the part, set what's next, record new decisions and gotchas).

If a step is too big for one response, split the phase into parts, tell me how many parts there are, and deliver them in order rather than shortening the code.

## Local environment
- Postgres is on host port **5433** (a native Postgres occupies 5432).
- Python 3.12 is managed by `uv`; always run Python via `uv run`, never the system Python.

## Commands
```
docker compose up -d                              # start Postgres + Redis (repo root)
uv run uvicorn app.main:app --reload --port 8000  # backend dev server (from backend/)
uv run pytest                                     # tests (from backend/; needs Docker up)
```
