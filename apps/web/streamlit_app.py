from pathlib import Path

import streamlit as st

from packages.core.logging_config import configure_logging
from packages.core.settings import get_settings
from packages.ingestion.pdf import delete_pdf_source, get_query_engine, pdf_data_dir, pdf_paths
from packages.llm.llama_index_settings import configure_llama_index
from packages.notes.engine import (
    answer_note_body,
    create_note,
    delete_note,
    export_notes_markdown,
    filter_notes,
    list_notes,
    update_note,
)
from packages.retrieval.vector_db import get_vector_store, indexed_sources

settings = get_settings()
configure_logging(settings)

st.set_page_config(page_title=settings.app_name, layout="wide")
DEFAULT_PROJECT_ID = "default"


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


def delete_source(source: str) -> None:
    deleted_file, deleted_chunks = delete_pdf_source(source)
    st.session_state.messages = []
    file_message = "deleted local PDF" if deleted_file else "local PDF was already missing"
    st.session_state.delete_message = (
        f"Removed {Path(source).name}: {file_message}, deleted {deleted_chunks} indexed chunk(s)."
    )
    st.rerun()


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


def source_node_text(source_node) -> str:
    node = source_node.node
    try:
        return node.get_content(metadata_mode="none")
    except TypeError:
        return node.get_content()
    except AttributeError:
        return getattr(node, "text", "")


def latex_friendly_markdown(text: str) -> str:
    return text.strip().replace("\n", "  \n")


def show_evidence(source_node, index: int) -> None:
    metadata = source_node.node.metadata or {}
    label = source_label(metadata) or f"Evidence {index}"
    score = getattr(source_node, "score", None)
    score_label = f" - score {score:.3f}" if isinstance(score, float) else ""

    with st.expander(f"{index}. {label}{score_label}"):
        st.markdown(latex_friendly_markdown(source_node_text(source_node)))


def parse_tags(value: str) -> list[str]:
    return [tag.strip() for tag in value.split(",") if tag.strip()]


def answer_paragraphs(answer: str) -> list[str]:
    return [paragraph.strip() for paragraph in answer.split("\n\n") if paragraph.strip()]


def citation_from_source_node(source_node) -> dict:
    metadata = source_node.node.metadata or {}
    return {
        "source": metadata.get("source"),
        "source_name": metadata.get("source_name"),
        "source_label": source_label(metadata),
        "page_start": metadata.get("page_start") or metadata.get("page_number"),
        "page_end": metadata.get("page_end")
        or metadata.get("page_start")
        or metadata.get("page_number"),
        "section_title": metadata.get("section_title"),
        "quoted_evidence": source_node_text(source_node),
    }


def citation_options() -> dict[str, dict]:
    citations = st.session_state.get("last_citations", [])
    return {
        f"{index}. {citation.get('source_label') or 'Source'}": citation
        for index, citation in enumerate(citations, start=1)
    }


def create_note_from_answer() -> None:
    answer = st.session_state.get("last_answer", "")
    paragraphs = answer_paragraphs(answer)
    paragraph_index = st.session_state.get("answer_note_paragraph", 0)
    if not paragraphs:
        st.warning("No answer is available to save.")
        return
    create_note(
        project_id=DEFAULT_PROJECT_ID,
        title=st.session_state.get("answer_note_title", "Answer note"),
        body=answer_note_body(answer, paragraphs[paragraph_index]),
        tags=parse_tags(st.session_state.get("answer_note_tags", "")),
        citations=st.session_state.get("last_citations", []),
        creation_method="selected_answer",
        source_type="answer",
    )
    st.success("Answer saved as a note.")


def create_note_from_citation(selected_label: str) -> None:
    citation = citation_options().get(selected_label)
    if not citation:
        st.warning("Select a citation first.")
        return
    create_note(
        project_id=DEFAULT_PROJECT_ID,
        title=st.session_state.get("citation_note_title", "Citation note"),
        body=citation.get("quoted_evidence", ""),
        tags=parse_tags(st.session_state.get("citation_note_tags", "")),
        citations=[citation],
        creation_method="selected_citation",
        source_type="citation",
    )
    st.success("Citation saved as a note.")


def create_ai_summary_note() -> None:
    answer = st.session_state.get("last_answer", "").strip()
    if not answer:
        st.warning("No answer is available to summarize.")
        return
    summary = answer_paragraphs(answer)[0] if answer_paragraphs(answer) else answer[:1200]
    create_note(
        project_id=DEFAULT_PROJECT_ID,
        title="AI summary note",
        body=answer_note_body(answer, summary),
        tags=["summary"],
        citations=st.session_state.get("last_citations", []),
        creation_method="ai_summary",
        source_type="answer",
    )
    st.success("AI summary note created.")


def show_notes_panel() -> None:
    st.header("Notes")

    create_tab, saved_tab, export_tab = st.tabs(["Create", "Saved", "Export"])

    with create_tab:
        citation_map = citation_options()
        with st.form("manual-note-form"):
            st.subheader("Manual note")
            title = st.text_input("Title", key="manual_note_title")
            body = st.text_area("Body", key="manual_note_body", height=160)
            tags = st.text_input("Tags", key="manual_note_tags", placeholder="tag1, tag2")
            selected_citations = st.multiselect(
                "Attach citations",
                list(citation_map),
                key="manual_note_citations",
            )
            submitted = st.form_submit_button("Save manual note")
            if submitted:
                create_note(
                    project_id=DEFAULT_PROJECT_ID,
                    title=title,
                    body=body,
                    tags=parse_tags(tags),
                    citations=[citation_map[label] for label in selected_citations],
                    creation_method="manual",
                    source_type="manual",
                )
                st.success("Manual note saved.")

        last_answer = st.session_state.get("last_answer", "")
        paragraphs = answer_paragraphs(last_answer)
        if paragraphs:
            st.subheader("Save from latest answer")
            st.text_input("Answer note title", value="Answer note", key="answer_note_title")
            st.text_input("Answer note tags", key="answer_note_tags", placeholder="tag1, tag2")
            st.selectbox(
                "Paragraph",
                range(len(paragraphs)),
                format_func=lambda index: paragraphs[index][:120],
                key="answer_note_paragraph",
            )
            if st.button("Save selected answer paragraph", width="stretch"):
                create_note_from_answer()
            if st.button("Create AI summary note", width="stretch"):
                create_ai_summary_note()

        if citation_map:
            st.subheader("Save from citation")
            selected_label = st.selectbox(
                "Citation", list(citation_map), key="citation_note_source"
            )
            st.text_input("Citation note title", value="Citation note", key="citation_note_title")
            st.text_input("Citation note tags", key="citation_note_tags", placeholder="tag1, tag2")
            if st.button("Save selected citation", width="stretch"):
                create_note_from_citation(selected_label)

    with saved_tab:
        notes = list_notes(DEFAULT_PROJECT_ID)
        all_tags = sorted({tag for note in notes for tag in note.get("tags", [])})
        search = st.text_input("Search notes")
        tag = st.selectbox(
            "Filter by tag", [""] + all_tags, format_func=lambda value: value or "All"
        )
        filtered_notes = filter_notes(notes, search=search, tag=tag)

        if not filtered_notes:
            st.caption("No notes found.")

        for note in filtered_notes:
            with st.expander(note.get("title", "Untitled note")):
                st.caption(
                    f"{note.get('creation_method', 'manual')} | {note.get('created_at', '')}"
                )
                title = st.text_input(
                    "Edit title", value=note.get("title", ""), key=f"title-{note['id']}"
                )
                body = st.text_area(
                    "Edit body",
                    value=note.get("body", ""),
                    key=f"body-{note['id']}",
                    height=160,
                )
                tags = st.text_input(
                    "Edit tags",
                    value=", ".join(note.get("tags", [])),
                    key=f"tags-{note['id']}",
                )
                if st.button("Save changes", key=f"save-{note['id']}"):
                    update_note(note["id"], title=title, body=body, tags=parse_tags(tags))
                    st.success("Note updated.")
                if st.button("Delete note", key=f"delete-{note['id']}"):
                    delete_note(note["id"])
                    st.rerun()

                citations = note.get("citations", [])
                if citations:
                    st.markdown("**Sources**")
                    for index, citation in enumerate(citations, start=1):
                        label = citation.get("source_label") or citation.get("source") or "Source"
                        st.caption(f"{index}. {label}")
                        if st.button("Open source", key=f"source-{note['id']}-{index}"):
                            st.info(citation.get("quoted_evidence", "No quoted evidence stored."))

    with export_tab:
        markdown = export_notes_markdown(DEFAULT_PROJECT_ID)
        st.download_button(
            "Download Markdown notes",
            data=markdown,
            file_name="evidenceflow-notes.md",
            mime="text/markdown",
            width="stretch",
        )
        st.markdown(markdown or "No notes to export.")


configure_llama_index()

st.title(settings.app_name)
st.caption(
    "Upload PDF files, store embeddings in Postgres/pgvector, and query the indexed documents."
)

with st.sidebar:
    st.header("Documents")
    if "delete_message" in st.session_state:
        st.success(st.session_state.pop("delete_message"))

    uploads = st.file_uploader(
        "Upload PDF files",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if st.button("Save and index", type="primary", width="stretch"):
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

    if st.button("Rebuild index", width="stretch"):
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
            for index, source in enumerate(sources):
                source_column, action_column = st.columns([0.72, 0.28])
                with source_column:
                    st.write(source)
                with action_column:
                    if st.button("Delete", key=f"delete-source-{index}", width="stretch"):
                        try:
                            delete_source(source)
                        except Exception as exc:
                            show_indexing_error(exc)
        else:
            st.caption("No indexed sources yet.")
    except Exception as exc:
        st.caption(f"Unable to read indexed sources: {exc}")

chat_column, divider_column, notes_column = st.columns(
    [0.64, 0.02, 0.34],
    gap="small",
    vertical_alignment="top",
)

with chat_column:
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
                st.session_state.last_answer = answer
                st.session_state.last_citations = [
                    citation_from_source_node(source_node) for source_node in source_nodes
                ]
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
                    with st.expander("Evidence text"):
                        for index, source_node in enumerate(source_nodes, start=1):
                            show_evidence(source_node, index)

                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as exc:
                error = f"Unable to answer from the indexed PDFs: {exc}"
                st.error(error)
                st.session_state.messages.append({"role": "assistant", "content": error})

with divider_column:
    st.markdown(
        """
        <div style="
            border-left: 1px solid rgba(49, 51, 63, 0.2);
            height: calc(100vh - 150px);
            margin: 0 auto;
        "></div>
        """,
        unsafe_allow_html=True,
    )

with notes_column:
    show_notes_panel()
