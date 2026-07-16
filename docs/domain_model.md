# Domain Model

```mermaid
erDiagram
    User ||--o{ ResearchProject : owns
    ResearchProject ||--o{ Document : contains
    ResearchProject ||--o{ Conversation : contains
    ResearchProject ||--o{ Note : contains
    Document ||--o{ DocumentPage : has
    Document ||--o{ DocumentSection : has
    Document ||--o{ Chunk : has
    Document ||--o{ ProcessingJob : has
    Document ||--o{ Citation : cited_by
    DocumentSection ||--o{ Chunk : groups
    Conversation ||--o{ Message : has
    Message ||--o{ Citation : supports
    Note ||--o{ Citation : supports
    Chunk ||--o{ Citation : evidence
```

## Deletion Behavior

- Deleting a `User` cascades to that user's `ResearchProject` records.
- Deleting a `ResearchProject` cascades to its documents, pages, sections,
  chunks, conversations, messages, notes, citations, and processing jobs.
- Deleting a `Document` cascades to its pages, sections, chunks, citations, and
  processing jobs.
- Deleting a `DocumentSection` keeps its chunks but sets `chunks.section_id` to
  null.
- Deleting a `Chunk` keeps citations but sets `citations.chunk_id` to null so
  the quoted evidence remains auditable.

## Duplicate Detection

Documents enforce a unique `(project_id, sha256_hash)` constraint so the same
PDF cannot be ingested twice into one project.
