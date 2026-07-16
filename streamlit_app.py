import base64
import html
import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from llm_settings import configure_llama_index
from pdf import get_query_engine, pdf_data_dir, pdf_paths
from vector_db import get_vector_store, indexed_sources


st.set_page_config(page_title="PDF RAG", layout="wide")

PDF_PREVIEW_MAX_BYTES = 25 * 1024 * 1024


def save_uploaded_files(uploaded_files) -> tuple[list[Path], bool]:
    data_dir = pdf_data_dir()
    saved_paths = []
    overwrote_existing_file = False

    for uploaded_file in uploaded_files:
        filename = Path(uploaded_file.name).name
        if not filename.lower().endswith(".pdf"):
            continue

        target_path = data_dir / filename
        overwrote_existing_file = overwrote_existing_file or target_path.exists()
        with target_path.open("wb") as file:
            file.write(uploaded_file.getbuffer())
        saved_paths.append(target_path)

    return saved_paths, overwrote_existing_file


def source_names() -> list[str]:
    vector_store = get_vector_store()
    return sorted(indexed_sources(vector_store))


def show_indexing_error(exc: Exception) -> None:
    st.error(str(exc))
    if exc.__cause__:
        st.caption(f"Cause: {exc.__cause__}")


def source_label(metadata: dict) -> str | None:
    source = metadata.get("source_name") or metadata.get("source")
    if not source:
        return None

    page_start = metadata.get("page_start") or metadata.get("page_number")
    page_end = metadata.get("page_end") or page_start
    section_title = metadata.get("section_title")

    parts = [str(source)]
    if page_start and page_end and page_start != page_end:
        parts.append(f"pages {page_start}-{page_end}")
    elif page_start:
        parts.append(f"page {page_start}")
    if section_title:
        parts.append(str(section_title))
    return " | ".join(parts)


def source_pdf_path(metadata: dict) -> Path | None:
    source = metadata.get("source")
    if not source:
        return None

    path = Path(str(source))
    if not path.is_absolute():
        path = Path.cwd() / path
    return path if path.exists() else None


def source_node_text(source_node) -> str:
    node = source_node.node
    try:
        return node.get_content(metadata_mode="none")
    except TypeError:
        return node.get_content()
    except AttributeError:
        return getattr(node, "text", "")


def highlighted_text_html(text: str, query: str) -> str:
    escaped_text = html.escape(text)
    terms = []
    for term in re.findall(r"[\w\u0600-\u06FF]{3,}", query):
        normalized = term.casefold()
        if normalized not in terms:
            terms.append(normalized)

    if terms:
        pattern = re.compile(
            "|".join(re.escape(html.escape(term)) for term in sorted(terms, key=len, reverse=True)),
            re.IGNORECASE,
        )
        escaped_text = pattern.sub(lambda match: f"<mark>{match.group(0)}</mark>", escaped_text)

    return escaped_text.replace("\n", "<br>")


def show_pdf_preview(path: Path, page_number) -> None:
    if path.stat().st_size > PDF_PREVIEW_MAX_BYTES:
        st.info("PDF is too large for inline preview.")
        with path.open("rb") as file:
            pdf_bytes = file.read()
        st.download_button(
            "Open downloaded PDF",
            data=pdf_bytes,
            file_name=path.name,
            mime="application/pdf",
            use_container_width=True,
        )
        return

    page = int(page_number or 1)
    with path.open("rb") as file:
        encoded_pdf = base64.b64encode(file.read()).decode("ascii")

    components.html(
        f"""
        <iframe
            src="data:application/pdf;base64,{encoded_pdf}#page={page}"
            width="100%"
            height="620"
            style="border: 1px solid #ddd; border-radius: 6px;"
            type="application/pdf">
        </iframe>
        """,
        height=640,
    )


def show_evidence(source_node, query: str, index: int) -> None:
    metadata = source_node.node.metadata or {}
    label = source_label(metadata) or f"Evidence {index}"
    score = getattr(source_node, "score", None)
    score_label = f" - score {score:.3f}" if isinstance(score, float) else ""

    with st.expander(f"{index}. {label}{score_label}"):
        st.markdown(
            f"""
            <div style="line-height:1.65; padding:0.75rem; border:1px solid #e5e7eb; border-radius:6px;">
                {highlighted_text_html(source_node_text(source_node), query)}
            </div>
            """,
            unsafe_allow_html=True,
        )

        pdf_path = source_pdf_path(metadata)
        if pdf_path:
            st.caption(f"PDF preview: {pdf_path.name}, page {metadata.get('page_start') or metadata.get('page_number') or 1}")
            show_pdf_preview(pdf_path, metadata.get("page_start") or metadata.get("page_number"))
        else:
            st.caption("PDF file was not found locally for preview.")


configure_llama_index()

st.title("PDF RAG")
st.caption("Upload PDF files, store embeddings in Postgres/pgvector, and query the indexed documents.")

with st.sidebar:
    st.header("Documents")
    uploads = st.file_uploader(
        "Upload PDF files",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if st.button("Save and index", type="primary", use_container_width=True):
        if not uploads:
            st.warning("Select at least one PDF file.")
        else:
            saved, overwrote_existing_file = save_uploaded_files(uploads)
            if saved:
                try:
                    with st.spinner("Indexing new PDF sources..."):
                        get_query_engine(rebuild=overwrote_existing_file)
                    st.success(f"Saved {len(saved)} file(s).")
                except Exception as exc:
                    show_indexing_error(exc)
            else:
                st.warning("No PDF files were saved.")

    if st.button("Rebuild index", use_container_width=True):
        try:
            with st.spinner("Rebuilding all local PDFs..."):
                get_query_engine(rebuild=True)
            st.success("Index rebuilt.")
        except Exception as exc:
            show_indexing_error(exc)

    local_files = pdf_paths()
    st.subheader("Local PDFs")
    if local_files:
        for path in local_files:
            st.write(path.name)
    else:
        st.caption("No local PDF files yet.")

    st.subheader("Indexed Sources")
    try:
        sources = source_names()
        if sources:
            for source in sources:
                st.write(source)
        else:
            st.caption("No indexed sources yet.")
    except Exception as exc:
        st.caption(f"Unable to read indexed sources: {exc}")

query = st.chat_input("Ask a question about the indexed PDFs")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Searching indexed PDFs..."):
                response = get_query_engine().query(query)

            answer = str(response)
            st.markdown(answer)

            source_nodes = getattr(response, "source_nodes", [])
            sources = []
            for source_node in source_nodes:
                metadata = source_node.node.metadata or {}
                label = source_label(metadata)
                if label and label not in sources:
                    sources.append(label)

            if sources:
                with st.expander("Sources"):
                    for source in sources:
                        st.write(source)

            if source_nodes:
                with st.expander("Evidence text and PDF pages"):
                    for index, source_node in enumerate(source_nodes, start=1):
                        show_evidence(source_node, query, index)

            st.session_state.messages.append({"role": "assistant", "content": answer})
        except Exception as exc:
            error = f"Unable to answer from the indexed PDFs: {exc}"
            st.error(error)
            st.session_state.messages.append({"role": "assistant", "content": error})
