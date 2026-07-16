CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(320) NOT NULL UNIQUE,
    display_name VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS research_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(300) NOT NULL,
    description TEXT,
    research_question TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_research_projects_owner_id
    ON research_projects(owner_id);

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    original_filename VARCHAR(500) NOT NULL,
    storage_path VARCHAR(1000) NOT NULL,
    sha256_hash CHAR(64) NOT NULL,
    title VARCHAR(500),
    authors JSONB,
    publication_year INTEGER,
    doi VARCHAR(255),
    page_count INTEGER,
    processing_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    processing_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_documents_project_sha256 UNIQUE (project_id, sha256_hash)
);

CREATE INDEX IF NOT EXISTS ix_documents_project_id ON documents(project_id);
CREATE INDEX IF NOT EXISTS ix_documents_sha256_hash ON documents(sha256_hash);
CREATE INDEX IF NOT EXISTS ix_documents_processing_status ON documents(processing_status);

CREATE TABLE IF NOT EXISTS document_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    text TEXT,
    metadata_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_document_pages_document_page UNIQUE (document_id, page_number)
);

CREATE INDEX IF NOT EXISTS ix_document_pages_document_id ON document_pages(document_id);
CREATE INDEX IF NOT EXISTS ix_document_pages_page_number ON document_pages(page_number);

CREATE TABLE IF NOT EXISTS document_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    title VARCHAR(300) NOT NULL,
    section_type VARCHAR(100) NOT NULL,
    section_index INTEGER NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_sections_document_index UNIQUE (document_id, section_index)
);

CREATE INDEX IF NOT EXISTS ix_document_sections_document_id ON document_sections(document_id);
CREATE INDEX IF NOT EXISTS ix_document_sections_page_range ON document_sections(page_start, page_end);

CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_id UUID REFERENCES document_sections(id) ON DELETE SET NULL,
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    token_count INTEGER,
    embedding vector,
    metadata_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_chunks_document_index UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS ix_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS ix_chunks_section_id ON chunks(section_id);
CREATE INDEX IF NOT EXISTS ix_chunks_page_range ON chunks(page_start, page_end);
CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    title VARCHAR(300),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_conversations_project_id ON conversations(project_id);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    metadata_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS ix_messages_created_at ON messages(created_at);

CREATE TABLE IF NOT EXISTS notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    title VARCHAR(300) NOT NULL,
    body TEXT NOT NULL,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    source_type VARCHAR(50) NOT NULL DEFAULT 'manual',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_notes_project_id ON notes(project_id);

CREATE TABLE IF NOT EXISTS citations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    note_id UUID REFERENCES notes(id) ON DELETE CASCADE,
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL,
    chunk_id UUID REFERENCES chunks(id) ON DELETE SET NULL,
    quoted_evidence TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_citations_note_or_message CHECK (
        note_id IS NOT NULL OR message_id IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS ix_citations_note_id ON citations(note_id);
CREATE INDEX IF NOT EXISTS ix_citations_message_id ON citations(message_id);
CREATE INDEX IF NOT EXISTS ix_citations_document_id ON citations(document_id);
CREATE INDEX IF NOT EXISTS ix_citations_chunk_id ON citations(chunk_id);

CREATE TABLE IF NOT EXISTS processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    job_type VARCHAR(100) NOT NULL DEFAULT 'ingestion',
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    processing_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_processing_jobs_document_id ON processing_jobs(document_id);
CREATE INDEX IF NOT EXISTS ix_processing_jobs_status ON processing_jobs(status);
