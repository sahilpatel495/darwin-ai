# Capacity — what one small instance carries, with no model

Half of DarwinLens never calls a model: the Overview dashboard and the ten guided analyses in
`backend/app/insights/` are templates over the catalog, run through the same guard, executor and
presentation code as a model-written query. That half has a real ceiling made of CPU, memory and
the session store, and it is a different ceiling from the model tier's. This document is that
ceiling, measured.

**The model tier is a separate limit and is deliberately not in here.** A question costs a free
provider's tokens, so its ceiling is a daily quota and a concurrency gate
(`MAX_CONCURRENT_ASKS`, `ASKS_PER_IP_PER_DAY`), not this machine. Mixing the two numbers would
produce one figure that is wrong about both. Every number below comes from a run where the
server was started with no `--env-file` and therefore had no provider key in its environment: no
model *could* be called, so the no-model claim is enforced by the setup rather than asserted.

Every figure here comes from `scripts/.loadtest/20260921-004936.json`, written by
`scripts/loadtest.py` (`make loadtest`). Nothing is estimated.

## The set-up

| | |
|---|---|
| Machine | Apple M3 Pro, 11 CPUs, 18.0 GB RAM, macOS 26.4.1 arm64, Python 3.12.13 |
| Server | `uvicorn app.main:app` on :8050, one process, one worker, started by the script |
| Hosted settings under test | `DUCKDB_MEMORY_LIMIT=256MB`, `DUCKDB_THREADS=2`, `MAX_SESSIONS=12`, `CROSSCHECK=off` — the same values `render.yaml` sets for the 512 MB free instance |
| Abuse limits | `SESSIONS_PER_IP_PER_HOUR`, `UPLOADS_PER_IP_PER_HOUR` and the ask limits raised to 100000 for the test, so the test measures the machine and not the limiter |
| Data | the bundled sample, `demo_data/` — 6 files, 0.36 MB, loaded through the real ingest path |
| Journey per analyst | guest token → create session → load sample → catalog → dashboard → analyses picker → four guided analyses (break down, trend, top and bottom, distribution) → table preview → delete session |

Two things the test could not change. `GUESTS_PER_HOUR` is hard-coded at 20 per address in
`app.limits`, so one guest token is minted per round and shared by that round's analysts — which
is also what one analyst in one browser does. And this is an M3 Pro, while the free Render
instance is 0.1 CPU: **the memory numbers transfer, the latency numbers do not.** Read the
latencies as a floor.

## The table

Rounds of 5, 15 and 30 analysts, each round run to completion before the next.

| Analysts at once | Wall clock | Completed | Evicted | Failed | Peak RSS | RSS at rest |
|---|---|---|---|---|---|---|
| 5 | 3.1 s | 5 | 0 | 0 | 208.4 MB | 202.7 MB |
| 15 | 12.1 s | 12 | 3 | 0 | 228.9 MB | 189.3 MB |
| 30 | 11.9 s | 12 | 18 | 0 | 246.6 MB | 245.3 MB |

Idle server, before any round: **157.1 MB** resident.

Per route, p50 / p95 / max in milliseconds, over the calls that succeeded:

| Route | 5 analysts | 15 analysts | 30 analysts |
|---|---|---|---|
| `POST /api/auth/guest` | 3.8 / 3.8 / 3.8 | 3.7 / 3.7 / 3.7 | 3.3 / 3.3 / 3.3 |
| `POST /api/sessions` | 14.9 / 15.5 / 15.5 | 29.2 / 37.1 / 37.1 | 77.5 / 93.1 / 93.9 |
| `POST /sample` (ingest) | 330.4 / 349.7 / 349.7 | 355.5 / 393.9 / 393.9 | 363.9 / 415.5 / 415.5 |
| `GET /catalog` | 1.4 / 1.5 / 1.5 | 1.5 / 1.7 / 1.7 | 1.5 / 2.0 / 2.0 |
| `GET /dashboard` | 52.9 / 70.6 / 70.6 | 55.1 / 70.0 / 70.0 | 54.0 / 64.9 / 64.9 |
| `GET /analyses` | 1.4 / 1.5 / 1.5 | 1.4 / 1.5 / 1.5 | 1.5 / 1.7 / 1.7 |
| `POST /analyses/run` (break down) | 2.7 / 3.6 / 3.6 | 2.8 / 3.3 / 3.3 | 3.0 / 3.9 / 3.9 |
| `POST /analyses/run` (trend) | 2.6 / 2.8 / 2.8 | 2.7 / 3.0 / 3.0 | 2.8 / 3.9 / 3.9 |
| `POST /analyses/run` (top and bottom) | 2.6 / 2.9 / 2.9 | 2.7 / 3.1 / 3.1 | 2.7 / 3.4 / 3.4 |
| `POST /analyses/run` (distribution) | 4.8 / 5.1 / 5.1 | 4.9 / 6.1 / 6.1 | 5.0 / 6.6 / 6.6 |
| `GET /preview` | 2.0 / 2.4 / 2.4 | 2.1 / 2.7 / 2.7 | 2.1 / 3.1 / 3.1 |
| `DELETE /api/sessions/{id}` | 1.8 / 2.0 / 2.0 | 2.0 / 3.7 / 3.7 | 2.0 / 2.7 / 2.7 |

## What saturates first, and at what concurrency

**`MAX_SESSIONS=12`, at the thirteenth concurrent analyst.** Nothing else came close. The store
is an LRU, so the thirteenth `POST /api/sessions` drops the least recently used session and its
owner meets the app's human 404 ("Your session has expired. Please upload your files again.").
The arithmetic is exact in the measurement: 15 analysts produced 3 evictions, 30 produced 18.
Twelve got through in every round.

It is not CPU. `GET /dashboard` — a dozen DuckDB queries, the most expensive no-model route —
held at 52.9, 55.1 and 54.0 ms p50 across 5, 15 and 30 analysts, and every guided analysis
stayed between 2.6 and 5.0 ms p50. On this machine the query work is not the constraint at any
concurrency the session store will allow.

It is not memory either: 246.6 MB peak against the 512 MB the hosted instance has.

Two things bend before the ceiling, and both are visible in the table:

- **Ingest is serial by design.** `limits.ingest()` is a semaphore of one for the whole host, so
  loading data queues for everybody. The successful loads barely slow down (330 → 364 ms p50),
  but the queue shows up as 429s: 10 of 15 sample loads were refused at 5 analysts, 66 of 81 at
  15, and 66 of 96 at 30. Each simulated analyst retried, which is why nothing failed. A real
  browser sees "Another upload is being read. Try again in a few seconds."
- **Session creation slows five-fold.** `POST /api/sessions` went 14.9 → 29.2 → 77.5 ms p50.
  Each one opens a DuckDB connection and runs nine lock-down statements, and the store's eviction
  happens under one lock. It is still under a tenth of a second at 30 analysts, so it is a note,
  not a problem.

## Memory per session

| Round | Sessions in the store | Peak RSS | Above idle |
|---|---|---|---|
| idle | 0 | 157.1 MB | — |
| 5 analysts | 5 | 208.4 MB | +51.3 MB |
| 15 analysts | 12 (the cap) | 228.9 MB | +71.8 MB |
| 30 analysts | 12 (the cap) | 246.6 MB | +89.5 MB |

The store can never hold more than 12, so **+89.5 MB is the whole session store at its ceiling**
— under 7.5 MB per session on the 0.36 MB sample, about 20× the size of the files, which is what
a profiled pandas frame plus a DuckDB table plus a catalog costs. Treat 7.5 MB as an upper bound
rather than a per-session constant: the figure also carries the transient cost of whichever
ingest was running when the peak was sampled, and the journeys start and finish at slightly
different moments, so the twelve are not all fully loaded at the same instant. The first session
costs more than the rest because it is what pulls pandas, openpyxl and the profiler into memory.

**Resident memory is sticky.** Deleting every session did not return it: 202.7 MB at rest after
the first round, 245.3 MB after the third, against a 157.1 MB floor. Size the host for the peak,
not for the idle figure.

## What the abuse limits do under load

The one-ingest-at-a-time gate was measured on its own: three analysts uploading the same
**14.78 MB** attendance CSV (`test_files/attendance_punches_2025.csv`) at the same moment.

- **1 accepted, 2 refused with 429**, immediately, with the app's two sentences and a
  `Retry-After` header. No 500s, no timeouts, nothing killed.
- The accepted upload took **3.78 s** end to end.
- Peak resident during it: **360.2 MB**, against 157.1 MB idle — **one 15 MB file costs 203 MB
  while it is being read in, 13.7× its own size.**

That last number is the whole argument for the semaphore. Two of these at once is roughly 400 MB
on top of the floor, which does not fit in 512 MB; the gate is what turns an OOM kill into a
sentence a person can act on. Afterwards, with all three sessions deleted, resident stayed at
250.1 MB — see "sticky", above.

Three limits were deliberately raised out of the way for this test and are worth naming, because
in production they are the first line and not the second: `SESSIONS_PER_IP_PER_HOUR` (5 on
Render, against 12 slots, so one address cannot evict everyone), `UPLOADS_PER_IP_PER_HOUR` (30)
and `GUESTS_PER_HOUR` (20, hard-coded). Also note that Render sets `MAX_UPLOAD_MB=10`, so the
15 MB file used here would be refused there with a 413 before any of this happened; the local
default of 25 MB is what let the gate be measured at all.

One gap this run confirms rather than closes: `GET /dashboard`, `GET /analyses`,
`POST /analyses/run`, `GET /catalog` and `GET /preview` are inside no rate limit at all (see
`docs/PENDING.md`). They are cheap here — 1.4 to 55 ms — but 55 ms of an 11-CPU machine is a good
deal more than 55 ms of 0.1 CPU, and nothing stops a loop over them.

## The honest scaling path

In the order the ceilings actually arrive:

1. **Sessions leave the process.** The 12-session ceiling is `SessionStore` being a dict in one
   worker. Move session metadata to Redis and give each session its own DuckDB file on object
   storage or a mounted disk, so a session outlives the process that made it and the ceiling
   becomes disk instead of RAM.
2. **The limiter moves to the proxy.** `SlidingWindow` counts in process memory, so two workers
   would keep two independent counts and a restart forgets every count. Rate limiting belongs in
   front of the app, where it also refuses a 15 MB body before Starlette has written it to disk.
3. **Model calls go behind a queue with per-tenant budgets.** `MAX_CONCURRENT_ASKS` refuses
   rather than queues, which is right for one instance and wrong for a tenant who paid. A real
   queue with a per-tenant token budget replaces "this demo is answering as many questions as it
   can right now" with a wait and a position.
4. **Accounts move to Postgres.** `app.auth` is SQLite on the instance's disk, which means one
   writer and no failover; the users table is the one piece of state that must survive the
   instance, so it is the one that has to move to a managed database first.
5. **Then, and only then, horizontal workers.** More than one worker is useless while sessions
   live in process memory, so until step 1 lands the interim is sticky routing by session id —
   honest, and it fails a whole worker's sessions when that worker restarts. After step 1,
   workers are stateless and scale on CPU.

## Reproducing this

```
make loadtest                                  # rounds of 5, 15, 30 plus the 15 MB upload round
uv run python scripts/loadtest.py --rounds 50  # one round of your own
uv run python scripts/loadtest.py --selftest   # the script's arithmetic, no server
```

The script starts and stops the server itself on :8050, samples `ps` once a second, prints the
table above and writes the raw numbers to `scripts/.loadtest/<timestamp>.json` (git-ignored). It
is stdlib only. It never sends a question to a model.
