# Breakscale server

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

Connect to `ws://localhost:8000/api/v1/simulations/stream` and send one JSON object
containing `graph` (nodes and edges), `duration_seconds` (default 10, maximum 300),
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
events are not paced to wall-clock seconds. Execution yields between batches but
each batch runs synchronously on the API event loop. This endpoint is intended for
modest local workloads. Production process workers, persistence, multiple
subscribers, windowed analytics, and utilization history remain future work.

### Saved simulation runs

Start the API with `uv run python main.py` and open `http://localhost:8000/docs`.
Seed the development user (`uv run python -m scripts.seed`), then create a workspace
with a valid architecture in `graph_data`.

- `POST /api/v1/simulations`: send `workspace_id`, `duration_seconds` (default 10,
  positive and at most 300), and `seed` (default 42). Returns the completed run
  with HTTP 201 after the simulation finishes.
- `GET /api/v1/simulations?workspace_id=UUID`: list workspace runs, newest first.
- `GET /api/v1/simulations/{id}`: retrieve run status and metadata.
- `GET /api/v1/simulations/{id}/results`: retrieve persisted summary and node metrics.

All simulation REST endpoints use the seeded development identity, check workspace
ownership, and return 403 when `DEBUG=false`. Use real authentication before public
deployment. These endpoints persist a graph snapshot and seed so later workspace
edits do not change the saved run. The engine executes through `asyncio.to_thread`
to keep synchronous work off the API event loop; this is not a production job queue.

The summary contains HTTP counters, throughput, error rate, latency percentiles,
background job counters/latency summaries, and retry metrics. Full latency samples
and time-series snapshots are not persisted. A completed run means its observation
window ended; jobs may still be queued or in flight.

Engine errors persist a failed run plus an error reason in the result's `summary`.
The POST error response includes `detail.simulation_id` for subsequent retrieval.
Cancellation, process crashes, or storage failures can still leave a running record;
reconciliation and durable workers remain future work. The existing PostgreSQL
models support this implementation without an additional migration.

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
advanced failures, live metrics/WebSockets, and frontend integration remain
future work. Cycles are rejected; requests also have a defensive 100-hop limit.

Run the unit suite with:

```sh
uv run pytest tests/unit -v
```
