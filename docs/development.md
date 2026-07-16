# Development

## Start the full stack

```powershell
docker compose up -d --build
```

Streamlit runs on `http://127.0.0.1:8501`.
The API health endpoint runs on `http://127.0.0.1:8000/health`.

## Database initialization

Docker Compose starts Postgres and applies every SQL file under
`infrastructure/migrations/` to fresh database volumes.

Run migrations manually against an existing database:

```powershell
uv run python scripts/run_migrations.py
```

Seed one example project:

```powershell
uv run python scripts/seed_example_project.py
```

The domain ERD and deletion behavior are documented in `docs/domain_model.md`.

## Quality checks

```powershell
uv run ruff check .
uv run mypy
uv run pytest
```

Run the Streamlit app locally:

```powershell
uv run streamlit run apps/web/streamlit_app.py
```
