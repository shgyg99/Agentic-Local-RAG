# AI Agent

A small command-line AI assistant built with LlamaIndex. The agent can answer
questions about world population data, retrieve information from indexed PDF
documents, and save user notes to a local text file.

The project is intentionally lightweight: data lives in the `data/` directory,
the app runs from `main.py`, and PDF vectors are stored in PostgreSQL with
pgvector so they do not need to be rebuilt every time.

## Features

- Interactive CLI agent powered by LlamaIndex `ReActAgent`
- OpenAI-compatible LLM configuration through `.env`
- Population questions answered from `data/population.csv`
- PDF document questions answered from files in `data/`
- Local note saving through a tool-backed `data/notes.txt` file
- PostgreSQL/pgvector-backed PDF retrieval for faster startup after the first run

## Project Structure

```text
AI-agent/
|-- data/
|   |-- Iran.pdf
|   |-- notes.txt
|   `-- population.csv
|-- main.py
|-- vector_db.py
|-- pdf.py
|-- note_engine.py
|-- pandas_query_engine.py
|-- prompts.py
|-- pyproject.toml
`-- README.md
```

## How It Works

`main.py` creates a ReAct agent with three tools:

- `note_saver`: appends notes to `data/notes.txt`
- `population_data`: queries the population CSV with a pandas query engine
- `pdf_documents`: queries the PDF-backed LlamaIndex engine

`vector_db.py` owns the PostgreSQL/pgvector connection and vector-store helpers.
`pdf.py` loads every PDF under `PDF_DATA_DIR`, adds `source`, `source_name`, and
`source_type` metadata to each document, indexes only sources that are not
already present in Postgres, and loads the existing vector table on later runs.

## Requirements

- Python 3.12 or newer
- `uv` for dependency management
- PostgreSQL with the `pgvector` extension enabled
- An OpenAI-compatible API key and model endpoint

Dependencies are declared in `pyproject.toml`.

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

POSTGRES_URL=postgresql://postgres:password@localhost:5432/vector_db
PGVECTOR_SCHEMA=public
PGVECTOR_TABLE=documents
PDF_DATA_DIR=data
REBUILD_VECTOR_INDEX=false
```

Notes:

- `API_KEY` is required for model calls.
- `API_URL` is optional if you are using the default OpenAI endpoint.
- `API_MODEL` should be a chat model supported by your provider.
- `EMBED_DIM` must match your embedding model. Use `3072` for
  `text-embedding-3-large`; use `1536` for `text-embedding-3-small` or
  `text-embedding-ada-002`.
- Each PDF chunk gets source metadata, for example
  `source=data/Iran.pdf`, so later retrieval and debugging can identify where
  the chunk came from.
- Set `REBUILD_VECTOR_INDEX=true` once when you want to clear and rebuild the
  Postgres vector table from the PDFs under `PDF_DATA_DIR`.

Create the database and extension before running the app:

```sql
CREATE DATABASE vector_db;
\c vector_db
CREATE EXTENSION IF NOT EXISTS vector;
```

## Run

Start the agent:

```powershell
uv run python main.py
```

Then ask a question:

```text
Enter a prompt (q to quit): What is the population of Iran?
```

Quit with:

```text
q
```

## Example Prompts

```text
What is the population of Iran?
```

```text
Tell me something about Iran from the PDF.
```

```text
Save a note that says: review the population data tomorrow.
```

## Generated Files

The app creates local runtime files:

- `data/notes.txt`: saved notes from the note tool
- `__pycache__/`: Python bytecode cache

These are ignored by `.gitignore` where appropriate.

## Security Notes

The pandas query engine executes model-generated pandas expressions against the
loaded dataframe. Use it only in a trusted local development environment.

Do not commit `.env`, API keys, or private notes.
