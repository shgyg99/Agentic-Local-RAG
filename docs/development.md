# Development

## Start the full stack

```powershell
docker compose up -d --build
```

Streamlit runs on `http://127.0.0.1:8501`.
The API health endpoint runs on `http://127.0.0.1:8000/health`.

## Database initialization

Docker Compose starts Postgres with pgvector enabled through
`docker/postgres/init/001-create-vector-extension.sql`.

The canonical migration file is:

```text
infrastructure/migrations/001_create_vector_extension.sql
```

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
