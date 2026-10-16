# Breakscale server

## Running the authenticated application

Configure `.env` from `.env.example`, set real PostgreSQL/Redis URLs, and generate
a private JWT secret. Redis URLs requiring TLS must use `rediss://`. Keep
`DEBUG=false`; no API route uses the old seeded development identity.

```sh
uv sync
uv run alembic upgrade head
uv run python main.py
# A separate terminal:
uv run python -m scripts.worker
# Frontend terminal, in client/:
npm run dev
```

Register at `http://localhost:3000/register`, then open the playground. Save the
workspace to PostgreSQL before Save & Run. That action saves the current canvas
again before submitting a job. History polls active runs; completed runs can be
compared, replayed, or deleted. The existing Save/Load buttons still use browser
IndexedDB, separately from server workspaces.

The worker launcher preserves TLS when spawning RQ child processes and uses the
JSON serializer. Use this launcher rather than a bare `rq worker` command.


## Database setup

1. Copy `.env.example` to `.env` if `.env` does not exist.
2. In Neon, open your project's **Connect** dialog and copy the connection string
   for the intended database and role into `DATABASE_URL` in `.env`. Replace all
   placeholders with real values. Keep `.env` private; it is ignored by Git.
   `postgresql://`, `postgres://`, and `postgresql+asyncpg://` are supported.
   Provider `sslmode` options are translated for asyncpg. URL-encode special
   characters in credentials when assembling a URL manually.
3. Verify connectivity:

   ```sh
   uv run python -m scripts.check_db
   ```

4. If there are no migrations yet, generate the initial migration:

   ```sh
   uv run alembic revision --autogenerate -m "create initial tables"
   ```

5. Review the generated migration, then apply it and check for schema differences:

   ```sh
   uv run alembic upgrade head
   uv run alembic check
   ```

On later checkouts, run `upgrade head` to apply existing migrations. Generate a
new revision only after changing models. The app and Alembic use the same settings
and model metadata; `.env` is resolved relative to the server directory. Exported
environment variables override `.env`, so unset a stale `DATABASE_URL` if needed.

An authentication failure means the server rejected the supplied credentials.
Check the selected Neon role and its current password; changing Python drivers
does not fix placeholder or expired credentials.

## Simulation component behavior

Load balancers support `round_robin` (default), `random`, and
`least_connections` through the node's `algorithm` setting. Least connections
uses each target's active resource count. Per-target routing counters are deferred
to a later iteration.

Cache nodes accept `cache_capacity` (default 1000) and `ttl_seconds` (default 60).
Requests share the default resource key. A miss fills the cache immediately and
continues downstream; a hit completes the request at the cache. Results include
`cache_hits`, `cache_misses`, and `cache_hit_rate` alongside component metrics.
This is a simplified linear read-path model: delayed fills and realistic miss
handling remain future work.

Database nodes use `pool_size` (default 10) to bound active connections. Services
use capacity, concurrency, and queue limits. The current processing time remains
`max(latency_ms / 1000, concurrency / capacity_rps)`; capacity and concurrency
semantics still need refinement to keep database pool size and throughput
consistent. Database locks and read/write query types are not modeled yet.

Queues use a FIFO message buffer with `queue_capacity` (default 1000). Workers
consume from their first upstream queue and process one attempt at a time.
Configure `processing_ms` (default 100), `failure_rate` (default 0), and
`max_attempts` (default 3) on each worker. Multiple workers can share a queue.
Workers require an incoming queue connection.

HTTP requests complete when publishing succeeds and fail when the queue is full.
Failed attempts retry after simulated exponential backoff (0.5, 1, 2, ... seconds,
capped at 30), without blocking consumption of other messages. Exhausted attempts
and retries rejected by a full queue are retained in the queue's `dead_letters`
list. Successful processing acknowledges the message.

Queue metrics include `published`, `consumed`, `acknowledged`, `rejected`,
`dead_lettered`, `depth`, and `in_flight`; worker metrics include `processed` and
`failed_attempts`. Published and consumed count retry operations too; depth counts
buffered messages, excluding active jobs and delayed retries. Metrics are snapshots
at the simulation cutoff; pending jobs and retries are not drained afterward.

Workers traverse downstream components, including database nodes, before
acknowledging a job. Downstream rejections retry the job from the worker, up to
its attempt limit. Nested queues and downstream worker/client nodes are rejected
explicitly. Background load balancers use their configured algorithm; caches on
background paths currently use generic processing without read-cache shortcuts.
Retries replay the whole job; transactional rollback and idempotency are not
modeled.

`SimulationResult.job_metrics` reports submitted jobs, completed jobs, dead-lettered
jobs, failed attempts, and successful job latencies from queue acceptance through
final acknowledgment (including retries). HTTP completion still means queue
acceptance. In-flight counts cover active attempts, excluding waiting messages
and delayed retries. Message completion timestamps and errors are retained.
Durable broker acknowledgments, worker crashes, and visibility timeouts are not
modeled. Time-series queue depth remains future work.

### Outages, circuit breakers, and timeouts

On service, database, cache, load-balancer, and other generic processing nodes,
set `failure_start_at` and `failure_duration` together to schedule an outage in
simulated seconds. Negative start times, nonpositive durations, and overlapping
outages on the same node are rejected. Outages affect entry into a component;
operations already processing continue.

Enable a consecutive-failure circuit breaker with `circuit_breaker_enabled`.
`failure_threshold` defaults to 5 and `recovery_timeout` to 5 simulated seconds.
After opening, the breaker rejects calls until the recovery delay expires, then
allows one half-open probe. A successful probe closes it; failure reopens it.
This is a simplified breaker, without rolling-window failure rates or complete
tracking of overlapping calls across circuit state changes.

`timeout_ms` sets a positive caller timeout, including component queue wait time.
By default, timed-out operations continue processing and occupying capacity;
they do not later turn the failed caller into a success. Set `cancel_on_timeout`
to `true` to interrupt the operation, release its resource, and remove any waiting
resource request. Interrupted operations do not increment processed counts.
Both HTTP requests and background jobs use
the same outage, breaker, and timeout execution path. Queue brokers and worker
processing itself are not covered by these component outage settings.

Component metrics include `failures`, `timeouts`, `outages`, `circuit_state`,
`circuit_open_count`, and `circuit_rejections`. Failures include rejected circuit
calls, unavailable components, timeouts, and component queue rejections.

### Component retries

Set `max_retries` from 0 (default) through 10 on a processing node. This adds
up to that many attempts after the initial attempt, including when a circuit
rejects a call. Configure positive `retry_base_delay` (default 0.5 seconds),
`retry_max_delay` (default 30 seconds), and `retry_jitter` from 0 to 1 (default
0.2). Backoff is exponential, capped before multiplying by a seeded random
factor between `1 - jitter` and `1 + jitter`. All waits use simulated time.

Each HTTP request records `attempts` and `retries` across its visited components.
`component_attempts` includes initial executions and retries for HTTP and
background paths; it excludes client arrivals, worker-local processing, and
queue publications. `total_retries` counts retries when they actually start,
excluding delays still pending at the simulation cutoff. `retry_amplification`
is component attempts divided by initial component attempts, or 1 for no
attempts. HTTP failure counters increment only when the request exhausts its
component retries. Background worker job retries remain separate and can amplify
component retries further. Retrying operations with cancellation disabled may
overlap backend work; retries do not imply rollback or idempotency.

### Metrics and WebSocket streaming

The engine supports `start()`, `advance(until)`, and `finalize()` as well as
`run()`. Start validates the graph before launching any processes and may only
be called once. Advance uses absolute simulated timestamps; finalize requires
the configured duration to be reached and aggregates final metrics once.
`MetricsCollector.capture()` reads independent snapshots of live counters
without finalizing the engine.

Connect to `ws://localhost:8000/api/v1/simulations/stream`. First send
`{ "ticket": "..." }` from authenticated `POST /api/v1/auth/ws-ticket`.
After `auth.authenticated`, send a second object containing `graph` (nodes and edges), `duration_seconds` (default 10, maximum 300),
`sample_interval` (default 1, range 0.1–300 seconds), `seed` (default 42), and
optional `max_requests` (default and maximum 10000).

The server sends objects with `type` and `data` fields:

- `simulation.started`: accepted duration and sample interval.
- `simulation.metrics`: a snapshot at each sample timestamp, including the final
  timestamp when the duration is not divisible by the interval.
- `simulation.completed`: the finalized simulation result, then a normal close.
- `simulation.error`: a validation/configuration error, then close code 1008.

Snapshots include interval throughput, cumulative error rate, exact linearly interpolated
latency percentiles (P50/P95/P99), queue depths, live component counters, background
job metrics, and retry amplification. Snapshot throughput is the change in completed
HTTP requests divided by simulated seconds since the preceding capture. Repeated
captures at the same timestamp return zero interval throughput. Persisted REST
summaries still use whole-run average throughput. Percentiles retain
all latency samples; streaming quantile estimators remain future work.

Each connection owns one run. Virtual time advances as fast as computation allows;
events are not paced to wall-clock seconds. Live simulations execute in an RQ child process; the API forwards ordered Redis
stream events. Disconnect sets a cooperative cancellation flag. Multiple
subscribers, windowed analytics, and utilization history remain future work.

### Saved simulation runs

Start the API with `uv run python main.py` and open `http://localhost:8000/docs`.
Register/login, then authorize Swagger with the access token and create a workspace
with a valid architecture in `graph_data`. Cookie endpoints also require an allowed
`Origin` header; browser forms supply it automatically.

- `POST /api/v1/simulations`: send `workspace_id`, `duration_seconds` (default 10,
  positive and at most 300), and `seed` (default 42). Returns a pending run
  with HTTP 202 after enqueueing; poll its status until it finishes.
- `GET /api/v1/simulations?workspace_id=UUID`: list workspace runs, newest first.
- `GET /api/v1/simulations/{id}`: retrieve run status and metadata.
- `GET /api/v1/simulations/{id}/results`: retrieve persisted summary and node metrics.

All resource endpoints require Bearer authentication and verify workspace ownership.
Snapshots preserve the graph and seed used for each run. The worker creates a
fresh SQLAlchemy engine/session lifecycle inside its own process. Never pass API
sessions to the worker.

The summary contains HTTP counters, throughput, error rate, latency percentiles,
background job counters/latency summaries, and retry metrics. Full latency samples
and time-series snapshots are not persisted. A completed run means its observation
window ended; jobs may still be queued or in flight.

Engine errors persist a failed run plus an error reason in the result summary.
Enqueue failures persist a failed record and return HTTP 503 with its ID.
`POST /simulations/{id}/cancel` cancels pending work or requests cooperative
cancellation between 0.25-second simulation batches. A final database row lock
prevents completion from overwriting an earlier cancellation request. Cancelled
runs can include partial metrics and trace. Active runs cannot be deleted.

Run `uv run python -m scripts.reconcile_simulations` periodically to identify
abandoned runs older than 16 minutes. Missing pending jobs are re-enqueued;
terminal/lost jobs are marked failed (or cancelled) with an error. Monitor RQ and
run this reconciler as a scheduled task; hard crashes cannot persist their own
errors. Redis enqueue and PostgreSQL are not a transactional outbox.

### Playground charts and node metrics

The playground displays throughput, P95 latency, error rate, and total message
queue depth across streamed snapshots. Click a node to inspect its counters;
click the canvas to clear selection. Nodes retain their connection handles and
show idle, healthy, busy, or overloaded badges. Queue badges use message depth
and in-flight work; generic component badges use `queued`, `active`, and failure
counters. Thresholds are provisional and cumulative rejections/failures can keep
a node marked overloaded after recovery. Worker-local activity is not yet sampled.

Use **Load overload example** for a Client (100 RPS) → API (50 RPS) → Database
(30 RPS) path with queue limits of five and a single database connection. Charts
advance in virtual time without playback pacing; badges do not animate individual
requests. Message queue depth excludes generic service/database waiting queues,
which are shown separately in the inspector.

Load-balancer health checks and weights, variable service latency,
and richer workload models remain future work. Cycles are rejected; requests also have a defensive 100-hop limit.

Run the unit suite with:

```sh
uv run pytest tests/unit -v
```


## Authentication and deployment

- `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout` and
  `GET /users/me` implement Argon2 credentials, 15-minute access JWTs, opaque
  refresh tokens stored only as SHA-256 hashes, and rotated refresh sessions.
  Reuse revokes the whole family. Logout revokes that family; access JWTs expire
  naturally rather than being individually blacklisted.
- Refresh cookies are HttpOnly with the auth route path, configurable Secure and
  SameSite flags. All cookie endpoints require an exact trusted Origin. For local
  HTTP use `COOKIE_SECURE=false`; HTTPS deployment must use true. SameSite=None
  requires Secure and remains protected by Origin checks. Prefer same-site custom
  domains for frontend/API; configure `ALLOWED_ORIGINS` for the actual frontend.
- Access tokens stay in browser memory. A single-flight refresh restores sessions;
  server resource ownership checks enforce authorization independently of UI gates.
- WebSocket tickets expire after 30 seconds and are atomically consumed once;
  access tokens never appear in WebSocket URLs. WebSocket Origin is checked before
  accepting commands. Limits bound request bodies, graph size, duration, request
  count, worker attempts, auth rate, and per-user concurrent jobs/streams.
- RQ jobs use a 600-second timeout, finite queue TTL, Redis leases, and fresh worker
  database sessions. Monitor queue delay, memory, quotas, retries, and recovery.
  Worker progress is published in Redis; saved history polls the owned REST API.

### Replay and historical comparisons

Each saved result retains up to 20000 synchronous HTTP trace events in nullable
`trace_data`. `/simulations/{id}/trace` checks ownership; old results return an
empty trace. Overflow is explicit (`truncated`, `dropped_events`). Replay uses a
separate read-only canvas from the saved graph snapshot, with play/pause, seek,
restart, and 0.5–4× speed. Markers interpolate between node entries and may include
service time; zero-duration transitions are skipped. Up to 200 markers are shown.
Background jobs and chart playback are not traced/synchronized yet. Comparison
shows missing historical metrics as N/A and preserves original architectures.

### Containers

At the project root, copy `compose.env.example` to a private local environment
file and set the database password and `COMPOSE_DATABASE_URL`. For the included
PostgreSQL service use hostname `postgres`, not localhost; URL-encode credentials.
Use the Neon URL instead if desired (the local database service is then optional).
The server `.env` supplies JWT/cookie/origin configuration; Compose overrides the
Redis URL with its internal Redis service. No secrets are copied into the image.

```sh
docker compose --env-file /path/to/private-compose.env up --build -d
# Controlled deployment step, once per deployment:
docker compose --env-file /path/to/private-compose.env run --rm api uv run --no-sync alembic upgrade head
docker compose --env-file /path/to/private-compose.env ps
docker compose --env-file /path/to/private-compose.env logs -f api worker
```

Use HTTPS/WSS, allowlisted origins, secure cookies, managed backups, restricted
Redis/database access, worker resource limits, monitoring and a scheduled
reconciler before deployment. Migrations must not run independently per replica.
This repository has not been deployed to a hosting provider.

### Quality and performance checks

```sh
uv run ruff check .
uv run mypy app
uv run pytest -v
# client/:
npx tsc --noEmit
npm run lint
npm test
npm run build
```

`uv run locust -f tests/performance/locustfile.py` starts a health smoke workload.
Set LOCUST_EMAIL, LOCUST_PASSWORD and LOCUST_WORKSPACE_ID for authenticated history
traffic against disposable resources. Measure representative simulation job CPU,
memory and queue/stream latency under concurrency before capacity planning;
a passing health test alone does not establish production capacity.

`uv run python -m scripts.benchmark` exercises linear, queue/worker, and
outage/retry workloads in two spawned engine processes, reporting wall time,
process peak memory, request counters and trace truncation. It excludes network,
API and Redis queue overhead. The opt-in full lifecycle test requires a running
worker and disposable test resources:

```sh
BREAKSCALE_INTEGRATION=1 uv run pytest tests/integration/test_full_lifecycle.py -v -s
```

Node connections use the green output below a node and the blue input above its
target. Drag between ports or click them in turn. The editor uses a dedicated
React Flow node type so default node styling cannot cover the custom handles.
