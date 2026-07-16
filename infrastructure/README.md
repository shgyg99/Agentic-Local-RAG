# Infrastructure

Development infrastructure is defined in `docker-compose.yml`.

Database initialization is defined by ordered SQL migrations in
`infrastructure/migrations/`.

Docker Compose mounts this folder into Postgres as
`/docker-entrypoint-initdb.d`, so a fresh development database applies the
migrations automatically. For an existing database, run:

```powershell
uv run python scripts/run_migrations.py
```
