import os
from pathlib import Path

from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex

from vector_db import clear_vector_store, env_flag, get_vector_store, indexed_sources


PDF_DATA_DIR = Path(os.getenv("PDF_DATA_DIR", "data"))
NUL_CHAR = "\x00"


def pdf_data_dir() -> Path:
    data_dir = Path(os.getenv("PDF_DATA_DIR", str(PDF_DATA_DIR)))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def normalized_source(file_path: str | Path) -> str:
    path = Path(file_path).resolve()
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def pdf_metadata(file_path: str) -> dict:
    path = Path(file_path)
    return {
        "source": clean_text(normalized_source(path)),
        "source_name": clean_text(path.name),
        "source_type": "pdf",
    }


def clean_text(value: str) -> str:
    return value.replace(NUL_CHAR, "")


def clean_metadata_value(value):
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, list):
        return [clean_metadata_value(item) for item in value]
    if isinstance(value, dict):
        return {key: clean_metadata_value(item) for key, item in value.items()}
    return value


def clean_document(document):
    content = document.get_content()
    if NUL_CHAR in content:
        document.set_content(clean_text(content))

    document.metadata = {
        key: clean_metadata_value(value)
        for key, value in document.metadata.items()
    }
    return document


def pdf_paths() -> list[Path]:
    data_dir = pdf_data_dir()
    return sorted(path for path in data_dir.rglob("*.pdf") if path.is_file())


def load_pdf_documents():
    paths = pdf_paths()
    if not paths:
        return []

    documents = SimpleDirectoryReader(
        input_files=paths,
        filename_as_id=True,
        file_metadata=pdf_metadata,
    ).load_data()
    return [clean_document(document) for document in documents]


def filter_new_documents(documents, known_sources: set[str]):
    return [
        document
        for document in documents
        if document.metadata.get("source") not in known_sources
    ]


def sync_pdf_index(index_name: str = "documents", rebuild: bool = False):
    vector_store = get_vector_store()
    rebuild_index = rebuild or env_flag("REBUILD_VECTOR_INDEX")

    if rebuild_index:
        print("clearing Postgres vector index", index_name)
        clear_vector_store(vector_store)
        known_sources = set()
    else:
        known_sources = indexed_sources(vector_store)

    documents = load_pdf_documents()
    new_documents = filter_new_documents(documents, known_sources)

    if new_documents:
        sources = sorted({document.metadata["source"] for document in new_documents})
        print("indexing PDF sources", sources)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        VectorStoreIndex.from_documents(
            new_documents,
            storage_context=storage_context,
            show_progress=True,
        )
        known_sources.update(sources)

    if not known_sources:
        raise FileNotFoundError(
            f"No indexed PDFs found. Upload or place PDF files in {pdf_data_dir()}."
        )

    print("loading Postgres vector index", index_name)
    return VectorStoreIndex.from_vector_store(vector_store=vector_store)


def get_query_engine(rebuild: bool = False):
    return sync_pdf_index(rebuild=rebuild).as_query_engine()
