from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.domain.models import (
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
    User,
)


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, email: str, display_name: str | None = None) -> User:
        user = User(email=email, display_name=display_name)
        self.session.add(user)
        self.session.flush()
        return user

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))


class ProjectRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        owner_id: str,
        title: str,
        description: str | None = None,
        research_question: str | None = None,
    ) -> ResearchProject:
        project = ResearchProject(
            owner_id=owner_id,
            title=title,
            description=description,
            research_question=research_question,
        )
        self.session.add(project)
        self.session.flush()
        return project

    def get(self, project_id: str) -> ResearchProject | None:
        return self.session.get(ResearchProject, project_id)

    def delete(self, project_id: str) -> bool:
        project = self.get(project_id)
        if project is None:
            return False
        self.session.delete(project)
        self.session.flush()
        return True


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        project_id: str,
        original_filename: str,
        storage_path: str,
        sha256_hash: str,
        title: str | None = None,
        authors: list[str] | None = None,
        publication_year: int | None = None,
        doi: str | None = None,
        page_count: int | None = None,
        processing_status: str = "pending",
        processing_error: str | None = None,
    ) -> Document:
        document = Document(
            project_id=project_id,
            original_filename=original_filename,
            storage_path=storage_path,
            sha256_hash=sha256_hash,
            title=title,
            authors=authors,
            publication_year=publication_year,
            doi=doi,
            page_count=page_count,
            processing_status=processing_status,
            processing_error=processing_error,
        )
        self.session.add(document)
        self.session.flush()
        return document

    def find_duplicate(self, *, project_id: str, sha256_hash: str) -> Document | None:
        return self.session.scalar(
            select(Document).where(
                Document.project_id == project_id,
                Document.sha256_hash == sha256_hash,
            )
        )

    def delete(self, document_id: str) -> bool:
        document = self.session.get(Document, document_id)
        if document is None:
            return False
        self.session.delete(document)
        self.session.flush()
        return True


class DocumentContentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_page(
        self,
        *,
        document_id: str,
        page_number: int,
        text: str | None = None,
        metadata_json: dict | None = None,
    ) -> DocumentPage:
        page = DocumentPage(
            document_id=document_id,
            page_number=page_number,
            text=text,
            metadata_json=metadata_json,
        )
        self.session.add(page)
        self.session.flush()
        return page

    def add_section(
        self,
        *,
        document_id: str,
        title: str,
        section_type: str,
        section_index: int,
        page_start: int | None = None,
        page_end: int | None = None,
    ) -> DocumentSection:
        section = DocumentSection(
            document_id=document_id,
            title=title,
            section_type=section_type,
            section_index=section_index,
            page_start=page_start,
            page_end=page_end,
        )
        self.session.add(section)
        self.session.flush()
        return section

    def add_chunk(
        self,
        *,
        document_id: str,
        page_start: int,
        page_end: int,
        chunk_index: int,
        text: str,
        section_id: str | None = None,
        token_count: int | None = None,
        embedding: list[float] | None = None,
        metadata_json: dict | None = None,
    ) -> Chunk:
        chunk = Chunk(
            document_id=document_id,
            section_id=section_id,
            page_start=page_start,
            page_end=page_end,
            chunk_index=chunk_index,
            text=text,
            token_count=token_count,
            embedding=embedding,
            metadata_json=metadata_json,
        )
        self.session.add(chunk)
        self.session.flush()
        return chunk


class ConversationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, project_id: str, title: str | None = None) -> Conversation:
        conversation = Conversation(project_id=project_id, title=title)
        self.session.add(conversation)
        self.session.flush()
        return conversation

    def add_message(
        self,
        *,
        conversation_id: str,
        role: str,
        content: str,
        metadata_json: dict | None = None,
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata_json=metadata_json,
        )
        self.session.add(message)
        self.session.flush()
        return message


class NoteRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        project_id: str,
        title: str,
        body: str,
        created_by: str | None = None,
        source_type: str = "manual",
    ) -> Note:
        note = Note(
            project_id=project_id,
            title=title,
            body=body,
            created_by=created_by,
            source_type=source_type,
        )
        self.session.add(note)
        self.session.flush()
        return note


class CitationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        document_id: str,
        page_start: int,
        page_end: int,
        quoted_evidence: str,
        note_id: str | None = None,
        message_id: str | None = None,
        chunk_id: str | None = None,
    ) -> Citation:
        citation = Citation(
            note_id=note_id,
            message_id=message_id,
            document_id=document_id,
            page_start=page_start,
            page_end=page_end,
            chunk_id=chunk_id,
            quoted_evidence=quoted_evidence,
        )
        self.session.add(citation)
        self.session.flush()
        return citation


class ProcessingJobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        document_id: str,
        job_type: str = "ingestion",
        status: str = "pending",
        attempts: int = 0,
        processing_error: str | None = None,
    ) -> ProcessingJob:
        job = ProcessingJob(
            document_id=document_id,
            job_type=job_type,
            status=status,
            attempts=attempts,
            processing_error=processing_error,
        )
        self.session.add(job)
        self.session.flush()
        return job
