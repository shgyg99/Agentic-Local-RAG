import os
import re
from collections import Counter
from pathlib import Path

from llama_index.core import Document, StorageContext, VectorStoreIndex
from pypdf import PdfReader

from vector_db import (
    clear_vector_store,
    delete_indexed_source,
    env_flag,
    get_vector_store,
    indexed_ingestion_versions,
    indexed_sources,
)


PDF_DATA_DIR = Path(os.getenv("PDF_DATA_DIR", "data"))
NUL_CHAR = "\x00"
INGESTION_VERSION = "page_section_v1"
MIN_SECTION_TEXT_LENGTH = 20

SECTION_ALIASES = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "background": "Introduction",
    "related work": "Introduction",
    "method": "Methods",
    "methods": "Methods",
    "methodology": "Methods",
    "materials and methods": "Methods",
    "experimental setup": "Methods",
    "results": "Results",
    "result": "Results",
    "findings": "Results",
    "discussion": "Discussion",
    "conclusion": "Conclusion",
    "conclusions": "Conclusion",
    "limitations": "Limitations",
    "limitation": "Limitations",
    "references": "References",
    "bibliography": "References",
}

SECTION_HEADING_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\.?\s+)?"
    r"(?P<title>"
    + "|".join(re.escape(title) for title in sorted(SECTION_ALIASES, key=len, reverse=True))
    + r")"
    r"\s*[:.]?\s*$",
    re.IGNORECASE,
)

WHITESPACE_RE = re.compile(r"[ \t]+")
BLANK_LINES_RE = re.compile(r"\n{3,}")


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


def normalize_line(line: str) -> str:
    return WHITESPACE_RE.sub(" ", clean_text(line)).strip()


def normalize_extracted_text(value: str) -> str:
    value = clean_text(value).replace("\r\n", "\n").replace("\r", "\n")
    lines = [normalize_line(line) for line in value.splitlines()]
    text = "\n".join(lines)
    text = BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def page_lines(raw_text: str) -> list[str]:
    return [
        line
        for line in (normalize_line(line) for line in raw_text.splitlines())
        if line
    ]


def repeated_margin_lines(pages: list[list[str]]) -> set[str]:
    if len(pages) < 3:
        return set()

    candidates = []
    for lines in pages:
        if lines:
            candidates.append(lines[0])
        if len(lines) > 1:
            candidates.append(lines[-1])

    minimum_repetitions = max(2, len(pages) // 2)
    return {
        line
        for line, count in Counter(candidates).items()
        if count >= minimum_repetitions and not SECTION_HEADING_RE.match(line)
    }


def remove_repeated_headers_and_footers(pages: list[list[str]]) -> list[list[str]]:
    repeated_lines = repeated_margin_lines(pages)
    if not repeated_lines:
        return pages

    cleaned_pages = []
    for lines in pages:
        cleaned = list(lines)
        if cleaned and cleaned[0] in repeated_lines:
            cleaned = cleaned[1:]
        if cleaned and cleaned[-1] in repeated_lines:
            cleaned = cleaned[:-1]
        cleaned_pages.append(cleaned)
    return cleaned_pages


def canonical_section_title(title: str | None) -> str:
    if not title:
        return "Unsectioned"
    normalized = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", title).strip().lower()
    return SECTION_ALIASES.get(normalized, title.strip().title())


def heading_title(line: str) -> str | None:
    match = SECTION_HEADING_RE.match(line)
    if not match:
        return None
    return canonical_section_title(match.group("title"))


def document_pdf_metadata(reader: PdfReader) -> dict:
    metadata = reader.metadata or {}
    title = getattr(metadata, "title", None) or metadata.get("/Title")
    author = getattr(metadata, "author", None) or metadata.get("/Author")
    values = {}
    if title:
        values["title"] = clean_text(str(title))
    if author:
        values["authors"] = clean_text(str(author))
    return values


def build_page_section_document(
    *,
    file_path: Path,
    text: str,
    page_number: int,
    page_count: int,
    section_title: str,
    section_index: int,
    pdf_info: dict,
) -> Document | None:
    normalized_text = normalize_extracted_text(text)
    if len(normalized_text) < MIN_SECTION_TEXT_LENGTH:
        return None

    metadata = {
        **pdf_metadata(str(file_path)),
        **clean_metadata_value(pdf_info),
        "ingestion_version": INGESTION_VERSION,
        "page_number": page_number,
        "page_start": page_number,
        "page_end": page_number,
        "page_count": page_count,
        "section_title": section_title,
        "section_type": section_title.lower().replace(" ", "_"),
        "section_index": section_index,
        "source_label": f"{file_path.name}, page {page_number}, {section_title}",
    }
    return clean_document(Document(text=normalized_text, metadata=metadata))


def extract_page_section_documents(file_path: Path) -> list[Document]:
    try:
        reader = PdfReader(str(file_path))
    except Exception as exc:
        raise ValueError(f"Could not read PDF file {file_path.name}.") from exc

    if reader.is_encrypted:
        raise ValueError(f"PDF file {file_path.name} is encrypted and cannot be indexed.")

    page_count = len(reader.pages)
    pdf_info = document_pdf_metadata(reader)
    extracted_pages = []
    for page in reader.pages:
        try:
            extracted_pages.append(page_lines(page.extract_text() or ""))
        except Exception:
            extracted_pages.append([])

    cleaned_pages = remove_repeated_headers_and_footers(extracted_pages)
    documents = []
    active_section = "Unsectioned"
    section_index = 0

    for page_index, lines in enumerate(cleaned_pages, start=1):
        buffer = []

        def flush_buffer() -> None:
            nonlocal section_index, buffer
            if not buffer:
                return
            document = build_page_section_document(
                file_path=file_path,
                text="\n".join(buffer),
                page_number=page_index,
                page_count=page_count,
                section_title=active_section,
                section_index=section_index,
                pdf_info=pdf_info,
            )
            if document is not None:
                documents.append(document)
                section_index += 1
            buffer = []

        for line in lines:
            title = heading_title(line)
            if title:
                flush_buffer()
                active_section = title
                continue
            buffer.append(line)

        flush_buffer()

    return documents


def pdf_paths() -> list[Path]:
    data_dir = pdf_data_dir()
    return sorted(path for path in data_dir.rglob("*.pdf") if path.is_file())


def source_pdf_path(source: str) -> Path:
    path = Path(source)
    if not path.is_absolute():
        path = Path.cwd() / path

    resolved_path = path.resolve()
    data_dir = pdf_data_dir().resolve()
    try:
        resolved_path.relative_to(data_dir)
    except ValueError as exc:
        raise ValueError(
            f"Refusing to delete {source!r} because it is outside {data_dir}."
        ) from exc

    return resolved_path


def delete_pdf_source(source: str) -> tuple[bool, int]:
    path = source_pdf_path(source)
    vector_store = get_vector_store()
    deleted_chunks = delete_indexed_source(vector_store, source)

    deleted_file = False
    if path.exists():
        path.unlink()
        deleted_file = True

    return deleted_file, deleted_chunks


def load_pdf_documents():
    paths = pdf_paths()
    if not paths:
        return []

    documents = []
    for path in paths:
        documents.extend(extract_page_section_documents(path))
    return documents


def filter_new_documents(documents, known_sources: set[str]):
    return [
        document
        for document in documents
        if document.metadata.get("source") not in known_sources
    ]


def sync_pdf_index(index_name: str = "documents", rebuild: bool = False):
    vector_store = get_vector_store()
    rebuild_index = rebuild or env_flag("REBUILD_VECTOR_INDEX")
    known_sources = set()
    if not rebuild_index:
        known_sources = indexed_sources(vector_store)
        versions = indexed_ingestion_versions(vector_store)
        rebuild_index = bool(known_sources) and versions != {INGESTION_VERSION}

    if rebuild_index:
        print("clearing Postgres vector index", index_name)
        clear_vector_store(vector_store)
        known_sources = set()

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
