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
