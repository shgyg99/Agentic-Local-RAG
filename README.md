# AI Agent

A small PDF RAG assistant built with LlamaIndex, Streamlit, and
PostgreSQL/pgvector. Upload PDF files, store their embeddings in Postgres, and
ask questions against the indexed documents.

## Features

- Streamlit UI for PDF upload and document Q&A
- Optional CLI agent in `main.py`
- OpenAI-compatible LLM configuration through `.env`
- PostgreSQL/pgvector-backed PDF retrieval
- Source metadata stored for every PDF chunk
- Local note saving through a tool-backed `data/notes.txt` file

## Project Structure

```text
AI-agent/
|-- data/
|   |-- Iran.pdf
|   `-- notes.txt
|-- streamlit_app.py
|-- main.py
|-- llm_settings.py
|-- vector_db.py
|-- pdf.py
|-- note_engine.py
|-- prompts.py
|-- pyproject.toml
`-- README.md
```

## How It Works

`streamlit_app.py` saves uploaded PDF files into `PDF_DATA_DIR`, then calls the
PDF indexing flow.

`vector_db.py` owns the PostgreSQL/pgvector connection and vector-store helpers.
`pdf.py` loads every PDF under `PDF_DATA_DIR`, adds `source`, `source_name`, and
`source_type` metadata to each document, indexes only sources that are not
already present in Postgres, and loads the existing vector table on later runs.

## Requirements

- Python 3.12 or newer
- `uv` for dependency management
- PostgreSQL with the `pgvector` extension enabled
- An OpenAI-compatible API key and model endpoint

## Setup

Install dependencies:

```powershell
uv sync
```

Create a `.env` file in the project root:

```env
API_KEY=your_api_key_here
API_URL=https://your-openai-compatible-endpoint/v1
API_MODEL=your-chat-model
EMBED_MODEL=text-embedding-3-large
EMBED_DIM=3072

# Optional. If omitted, the app builds a local URL from the values below.
# POSTGRES_URL=postgresql://postgres:your_real_password@localhost:5432/vector_db
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
```

If `POSTGRES_URL` is not set, the app uses the local Postgres settings above.
The included Docker Compose service publishes Postgres on host port `5433` to
avoid conflicts with a local Postgres installation on `5432`.

Start the full Docker stack:

```powershell
docker compose up -d --build
```

Then open:

```text
http://127.0.0.1:8501
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

The app also runs `CREATE EXTENSION IF NOT EXISTS vector` through LlamaIndex
when the connected user has permission.

`EMBED_DIM` must match your embedding model. Use `3072` for
`text-embedding-3-large`; use `1536` for `text-embedding-3-small` or
`text-embedding-ada-002`.

Set `REBUILD_VECTOR_INDEX=true` once when you want to clear and rebuild the
Postgres vector table from the PDFs under `PDF_DATA_DIR`.

## Run

Start the Streamlit app locally without Docker:

```powershell
uv run streamlit run streamlit_app.py
```

Or run the CLI agent:

```powershell
uv run python main.py
```

## Source Metadata

Each PDF chunk stores metadata like this:

```python
{
    "source": "data/Iran.pdf",
    "source_name": "Iran.pdf",
    "source_type": "pdf",
}
```

## Generated Files

- `data/notes.txt`: saved notes from the note tool
- `__pycache__/`: Python bytecode cache

Do not commit `.env`, API keys, or private notes.
