# AI Agent

A small command-line AI assistant built with LlamaIndex. The agent can answer
questions about world population data, retrieve information from an Iran PDF
document, and save user notes to a local text file.

The project is intentionally lightweight: data lives in the `data/` directory,
the app runs from `main.py`, and generated indexes are persisted locally so they
do not need to be rebuilt every time.

## Features

- Interactive CLI agent powered by LlamaIndex `ReActAgent`
- OpenAI-compatible LLM configuration through `.env`
- Population questions answered from `data/population.csv`
- Iran document questions answered from `data/Iran.pdf`
- Local note saving through a tool-backed `data/notes.txt` file
- Persisted LlamaIndex storage in `Iran/` for faster startup after the first run

## Project Structure

```text
AI-agent/
|-- data/
|   |-- Iran.pdf
|   |-- notes.txt
|   `-- population.csv
|-- main.py
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
- `Iran_data`: queries the PDF-backed LlamaIndex engine for Iran-related details

`pdf.py` loads `data/Iran.pdf` with `SimpleDirectoryReader`, builds a
`SummaryIndex`, and persists the result in the local `Iran/` directory.

## Requirements

- Python 3.12 or newer
- `uv` for dependency management
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
EMBED_MODEL=text-embedding-ada-002
```

Notes:

- `API_KEY` is required for model calls.
- `API_URL` is optional if you are using the default OpenAI endpoint.
- `API_MODEL` should be a chat model supported by your provider.
- `EMBED_MODEL` is read by `main.py`; the current PDF index uses `SummaryIndex`,
  so embeddings are not required for building that PDF index.

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

- `Iran/`: persisted LlamaIndex storage for the Iran PDF index
- `data/notes.txt`: saved notes from the note tool
- `__pycache__/`: Python bytecode cache

These are ignored by `.gitignore` where appropriate.

## Security Notes

The pandas query engine executes model-generated pandas expressions against the
loaded dataframe. Use it only in a trusted local development environment.

Do not commit `.env`, API keys, or private notes.
