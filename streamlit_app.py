from pathlib import Path

import streamlit as st

from llm_settings import configure_llama_index
from pdf import get_query_engine, pdf_data_dir, pdf_paths
from vector_db import get_vector_store, indexed_sources


st.set_page_config(page_title="PDF RAG", layout="wide")


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

            sources = []
            for source_node in getattr(response, "source_nodes", []):
                metadata = source_node.node.metadata or {}
                source = metadata.get("source")
                if source and source not in sources:
                    sources.append(source)

            if sources:
                with st.expander("Sources"):
                    for source in sources:
                        st.write(source)

            st.session_state.messages.append({"role": "assistant", "content": answer})
        except Exception as exc:
            error = f"Unable to answer from the indexed PDFs: {exc}"
            st.error(error)
            st.session_state.messages.append({"role": "assistant", "content": error})
