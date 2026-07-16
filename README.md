# EvidenceFlow

EvidenceFlow is a research-reading and note-taking application built with
LlamaIndex, Streamlit, and PostgreSQL/pgvector. It is designed for working
through academic papers: upload and index PDFs, ask grounded questions, save
AI-assisted notes with their evidence, and compare related papers you add to
understand the direction and context of a research path.

The app is not a general-purpose chat tool. Its focus is helping researchers
turn a collection of papers into a traceable understanding of the literature:
what each paper says, how methods and findings relate, and which questions are
worth investigating next.

## Screenshot

![EvidenceFlow app screenshot](Screenshot.png)

## Features

- Streamlit workspace for reading papers, document Q&A, and note-taking
- Paper-grounded Q&A for methods, findings, limitations, and terminology
- FastAPI service with health-check and note endpoints
- Optional CLI agent in `apps/cli.py`
- OpenAI-compatible LLM configuration through `.env`
- PostgreSQL/pgvector-backed PDF retrieval
- SQLAlchemy domain model with project, document, chunk, citation, note, and job records
- Page-aware and section-aware source metadata stored for every PDF chunk
- Notes include the AI answer or selected answer text alongside its sources
- Local note storage in `data/notes.json`, plus a CLI note tool that can append
  to `data/notes.txt`

## Project Structure

```text
AI-agent/
|-- apps/
|   |-- api/
|   `-- web/
|-- packages/
|   |-- ingestion/
|   |-- retrieval/
|   |-- llm/
|   |-- domain/
|   `-- evaluation/
|-- infrastructure/
|   `-- migrations/
|-- tests/
|-- docs/
|-- data/                 # local PDFs and generated notes, gitignored
|-- docker/
|-- Screenshot.png
|-- pyproject.toml
`-- README.md
```

## Research Workflow

1. Add the papers relevant to a research topic.
2. Ask questions about methods, results, limitations, and terminology while
   reading.
3. Use the answers and retrieved evidence to clarify terminology and compare
   claims across the uploaded reading set.
4. Save useful answers as notes. Each note keeps the AI answer and the source
   passages that support it.
5. Compare the evidence across papers to identify related work, recurring
   methods, open gaps, and the next direction for the research.

This workflow makes the connection between a note and its source explicit, so
the resulting research trail remains reviewable rather than becoming a set of
detached summaries.

## How It Works

`apps/web/streamlit_app.py` saves uploaded PDF files into `PDF_DATA_DIR`, then
calls the PDF indexing flow.

`packages/retrieval/vector_db.py` owns the PostgreSQL/pgvector connection and
vector-store helpers. `packages/ingestion/pdf.py` loads every PDF under
`PDF_DATA_DIR`, extracts text page by page, splits page text when common academic
section headings are detected, and stores page and section metadata with each
indexed document. It indexes only sources that are not already present in
Postgres, rebuilds when `REBUILD_VECTOR_INDEX=true` or the ingestion version
changes, and loads the existing vector table on later runs.

`packages/core/settings.py` validates environment-driven configuration with
Pydantic Settings. `packages/core/logging_config.py` configures JSON structured
logging. `apps/api/main.py` exposes `/health`, note create/list/export endpoints,
and a global exception handler.

## Requirements

- Python 3.12 or newer
- `uv` for dependency management
- PostgreSQL with the `pgvector` extension enabled
- An API key, chat model name, and optional OpenAI-compatible model endpoint

## Setup

Install dependencies:

```powershell
uv sync
```

Create a `.env` file in the project root:

```env
API_KEY=your_api_key_here
# Optional when using the default OpenAI API.
# API_URL=https://your-openai-compatible-endpoint/v1
API_MODEL=your-chat-model
EMBED_MODEL=text-embedding-3-large
EMBED_DIM=3072
APP_NAME=EvidenceFlow
APP_ENV=development
LOG_LEVEL=INFO
LOG_FORMAT=json

# Optional. If omitted, the app builds a local URL from the values below.
# POSTGRES_URL=postgresql://postgres:your_real_password@localhost:5433/vector_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_real_password
POSTGRES_DB=vector_db
POSTGRES_AUTO_CREATE_DB=true
PGVECTOR_SCHEMA=public
PGVECTOR_TABLE=documents
PDF_DATA_DIR=data
REBUILD_VECTOR_INDEX=false
STREAMLIT_PORT=8501
API_PORT=8000
```

If `POSTGRES_URL` is not set, the app uses the local Postgres settings above.
The included Docker Compose service publishes Postgres on host port `5433` to
avoid conflicts with a local Postgres installation on `5432`. Inside Docker,
the app services connect to the `postgres` service on port `5432`.

Start the full Docker stack:

```powershell
docker compose up -d --build
```

Then open:

```text
http://127.0.0.1:8501
```

Backend health check:

```text
http://127.0.0.1:8000/health
```

Start only Postgres with pgvector:

```powershell
docker compose up -d postgres
```

Stop it:

```powershell
docker compose down
```

If `POSTGRES_URL` is set, automatic database creation only runs when
`POSTGRES_AUTO_CREATE_DB=true`.

If you create the database manually, run:

```sql
CREATE DATABASE vector_db;
\c vector_db
CREATE EXTENSION IF NOT EXISTS vector;
```

The canonical database initialization SQL is documented in:

```text
infrastructure/migrations/
```

Run migrations manually against an existing database:

```powershell
uv run python scripts/run_migrations.py
```

Seed a demo user and project:

```powershell
uv run python scripts/seed_example_project.py
```

`EMBED_DIM` must match your embedding model. Use `3072` for
`text-embedding-3-large`; use `1536` for `text-embedding-3-small` or
`text-embedding-ada-002`.

Set `REBUILD_VECTOR_INDEX=true` once when you want to clear and rebuild the
Postgres vector table from the PDFs under `PDF_DATA_DIR`.

## Run

Start the Streamlit app locally without Docker:

```powershell
uv run streamlit run apps/web/streamlit_app.py
```

Or run the CLI agent:

```powershell
uv run python apps/cli.py
```

Run the FastAPI service locally:

```powershell
uv run uvicorn apps.api.main:app --reload
```

## Quality Checks

Install all dependency groups:

```powershell
uv sync --all-groups
```

Run lint, type checking, and tests:

```powershell
uv run ruff check .
uv run mypy
uv run pytest
```

Install pre-commit hooks:

```powershell
uv run pre-commit install
```

CI runs the same checks on pushes to `main` and on pull requests.

## Domain Database Schema

The domain schema in `infrastructure/migrations/` and
`packages/domain/models.py` includes:

- `users`
- `research_projects`
- `documents`
- `document_pages`
- `document_sections`
- `chunks`
- `conversations`
- `messages`
- `citations`
- `notes`
- `processing_jobs`

See [docs/domain_model.md](docs/domain_model.md) for the ERD, duplicate document
constraint, and deletion behavior.

The SQLAlchemy repository layer lives in
`packages/domain/repositories.py`. Unit tests cover duplicate document detection,
project cascade deletion, and citation traceability.

## Source Metadata

Each PDF chunk stores metadata like this:

```python
{
    "source": "data/paper.pdf",
    "source_name": "paper.pdf",
    "source_type": "pdf",
    "ingestion_version": "page_section_v1",
    "page_number": 4,
    "page_start": 4,
    "page_end": 4,
    "page_count": 12,
    "section_title": "Methods",
    "section_type": "methods",
    "section_index": 5,
    "source_label": "paper.pdf, page 4, Methods",
}
```

Section detection covers common academic headings including Abstract,
Introduction, Methods, Results, Discussion, Conclusion, Limitations, and
References. The Streamlit source panel renders retrieved evidence as document,
page, and section labels.

## Generated Files

- `data/*.pdf`: local PDFs uploaded through Streamlit or placed under `PDF_DATA_DIR`
- `data/notes.json`: notes created through Streamlit or the FastAPI note endpoints
- `data/notes.txt`: notes appended by the CLI `note_saver` tool
- `__pycache__/`: Python bytecode cache

Do not commit `.env`, API keys, or private notes.
