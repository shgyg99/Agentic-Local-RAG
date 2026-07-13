import os
from pathlib import Path

from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex

from vector_db import clear_vector_store, env_flag, get_vector_store, indexed_sources


PDF_DATA_DIR = Path(os.getenv("PDF_DATA_DIR", "data"))


def _normalized_source(file_path: str | Path) -> str:
    path = Path(file_path).resolve()
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def _pdf_metadata(file_path: str) -> dict:
    path = Path(file_path)
    return {
        "source": _normalized_source(path),
        "source_name": path.name,
        "source_type": "pdf",
    }


def load_pdf_documents():
    if not PDF_DATA_DIR.exists():
        raise FileNotFoundError(f"PDF data directory does not exist: {PDF_DATA_DIR}")

    documents = SimpleDirectoryReader(
        input_dir=PDF_DATA_DIR,
        recursive=True,
        required_exts=[".pdf"],
        filename_as_id=True,
        file_metadata=_pdf_metadata,
    ).load_data()

    if not documents:
        raise FileNotFoundError(f"No PDF files found in: {PDF_DATA_DIR}")

    return documents


def _filter_new_documents(documents, known_sources: set[str]):
    return [
        document
        for document in documents
        if document.metadata.get("source") not in known_sources
    ]


def get_index(index_name: str = "documents"):
    vector_store = get_vector_store()
    rebuild_index = env_flag("REBUILD_VECTOR_INDEX")

    if rebuild_index:
        print("clearing Postgres vector index", index_name)
        clear_vector_store(vector_store)
        known_sources = set()
    else:
        known_sources = indexed_sources(vector_store)

    documents = load_pdf_documents()
    new_documents = _filter_new_documents(documents, known_sources)

    if new_documents:
        sources = sorted({document.metadata["source"] for document in new_documents})
        print("indexing PDF sources", sources)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        return VectorStoreIndex.from_documents(
            new_documents,
            storage_context=storage_context,
            show_progress=True,
        )

    print("loading Postgres vector index", index_name)
    return VectorStoreIndex.from_vector_store(vector_store=vector_store)


document_index = get_index("documents")
document_engine = document_index.as_query_engine()

# Backward-compatible alias used by main.py.
Iran_engine = document_engine
