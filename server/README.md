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

Load-balancer health checks and weights, variable service latency,
advanced failures, live metrics/WebSockets, and frontend integration remain
future work. Cycles are rejected; requests also have a defensive 100-hop limit.

Run the unit suite with:

```sh
uv run pytest tests/unit -v
```
