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

Queues and workers currently use generic component processing. Producer/consumer
processing, backlog, acknowledgments, retries, and dead-letter queues are the next
stage. Load-balancer health checks and weights, variable service latency,
advanced failures, live metrics/WebSockets, and frontend integration remain
future work. Cycles are rejected; requests also have a defensive 100-hop limit.

Run the unit suite with:

```sh
uv run pytest tests/unit -v
```
