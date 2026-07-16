from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.domain.models import (
    Base,
    Chunk,
    Citation,
    Conversation,
    Document,
    DocumentPage,
    DocumentSection,
    Message,
    Note,
    ProcessingJob,
    ResearchProject,
)
from packages.domain.repositories import (
    CitationRepository,
    ConversationRepository,
    DocumentContentRepository,
    DocumentRepository,
    NoteRepository,
    ProcessingJobRepository,
    ProjectRepository,
    UserRepository,
)


@pytest.fixture
def session() -> Generator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, future=True) as session:
        yield session


def create_project(session: Session) -> tuple[str, str]:
    user = UserRepository(session).create(email="researcher@example.com")
    project = ProjectRepository(session).create(
        owner_id=user.id,
        title="Evidence project",
        research_question="What evidence is available?",
    )
    return user.id, project.id


def create_document(session: Session, project_id: str, sha256_hash: str = "a" * 64) -> Document:
    return DocumentRepository(session).create(
        project_id=project_id,
        original_filename="paper.pdf",
        storage_path="data/paper.pdf",
        sha256_hash=sha256_hash,
        title="Paper",
        page_count=2,
        processing_status="ready",
    )


def count_rows(session: Session, model: type[Base]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_duplicate_document_hash_is_detectable_and_constrained(session: Session) -> None:
    _, project_id = create_project(session)
    documents = DocumentRepository(session)
    original = create_document(session, project_id)

    duplicate = documents.find_duplicate(project_id=project_id, sha256_hash=original.sha256_hash)

    assert duplicate is not None
    assert duplicate.id == original.id

    with pytest.raises(IntegrityError):
        documents.create(
            project_id=project_id,
            original_filename="copy.pdf",
            storage_path="data/copy.pdf",
            sha256_hash=original.sha256_hash,
        )


def test_project_delete_cascades_dependent_records(session: Session) -> None:
    user_id, project_id = create_project(session)
    document = create_document(session, project_id)
    content = DocumentContentRepository(session)
    page = content.add_page(document_id=document.id, page_number=1, text="Evidence text")
    section = content.add_section(
        document_id=document.id,
        title="Methods",
        section_type="methods",
        section_index=0,
        page_start=1,
        page_end=1,
    )
    chunk = content.add_chunk(
        document_id=document.id,
        section_id=section.id,
        page_start=1,
        page_end=1,
        chunk_index=0,
        text="Evidence text",
    )
    conversation = ConversationRepository(session).create(project_id=project_id)
    message = ConversationRepository(session).add_message(
        conversation_id=conversation.id,
        role="assistant",
        content="Answer",
    )
    note = NoteRepository(session).create(
        project_id=project_id,
        title="Finding",
        body="Evidence note",
        created_by=user_id,
    )
    CitationRepository(session).create(
        note_id=note.id,
        message_id=message.id,
        document_id=document.id,
        chunk_id=chunk.id,
        page_start=1,
        page_end=1,
        quoted_evidence="Evidence text",
    )
    ProcessingJobRepository(session).create(document_id=document.id, status="ready")
    session.commit()

    assert page.id
    ProjectRepository(session).delete(project_id)
    session.commit()

    for model in (
        ResearchProject,
        Document,
        DocumentPage,
        DocumentSection,
        Chunk,
        Conversation,
        Message,
        Note,
        Citation,
        ProcessingJob,
    ):
        assert count_rows(session, model) == 0


def test_note_citation_traces_back_to_document_and_chunk(session: Session) -> None:
    user_id, project_id = create_project(session)
    document = create_document(session, project_id)
    section = DocumentContentRepository(session).add_section(
        document_id=document.id,
        title="Results",
        section_type="results",
        section_index=0,
        page_start=2,
        page_end=2,
    )
    chunk = DocumentContentRepository(session).add_chunk(
        document_id=document.id,
        section_id=section.id,
        page_start=2,
        page_end=2,
        chunk_index=0,
        text="The model improved accuracy.",
    )
    note = NoteRepository(session).create(
        project_id=project_id,
        title="Accuracy",
        body="Accuracy improved.",
        created_by=user_id,
        source_type="citation",
    )
    citation = CitationRepository(session).create(
        note_id=note.id,
        document_id=document.id,
        chunk_id=chunk.id,
        page_start=2,
        page_end=2,
        quoted_evidence="The model improved accuracy.",
    )
    session.commit()

    stored = session.get(Citation, citation.id)

    assert stored is not None
    assert stored.document.original_filename == "paper.pdf"
    assert stored.chunk is not None
    assert stored.chunk.text == "The model improved accuracy."
    assert stored.note is not None
    assert stored.note.project_id == project_id
