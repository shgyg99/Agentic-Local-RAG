import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llama_index.core.tools import FunctionTool

note_file = os.path.join("data", "notes.txt")
NOTES_JSON_FILE = Path(os.getenv("NOTES_JSON_FILE", "data/notes.json"))


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def notes_path() -> Path:
    NOTES_JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    return NOTES_JSON_FILE


def load_notes() -> list[dict[str, Any]]:
    path = notes_path()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_notes(notes: list[dict[str, Any]]) -> None:
    notes_path().write_text(
        json.dumps(notes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_notes(project_id: str = "default") -> list[dict[str, Any]]:
    return [note for note in load_notes() if note.get("project_id") == project_id]


def create_note(
    *,
    title: str,
    body: str,
    project_id: str = "default",
    tags: list[str] | None = None,
    citations: list[dict[str, Any]] | None = None,
    creation_method: str = "manual",
    source_type: str = "manual",
) -> dict[str, Any]:
    now = utc_now_iso()
    note = {
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "title": title.strip() or "Untitled note",
        "body": body.strip(),
        "tags": tags or [],
        "citations": citations or [],
        "creation_method": creation_method,
        "source_type": source_type,
        "created_at": now,
        "updated_at": now,
    }
    notes = load_notes()
    notes.append(note)
    save_notes(notes)
    return note


def update_note(
    note_id: str,
    *,
    title: str,
    body: str,
    tags: list[str] | None = None,
) -> dict[str, Any] | None:
    notes = load_notes()
    for note in notes:
        if note.get("id") == note_id:
            note["title"] = title.strip() or "Untitled note"
            note["body"] = body.strip()
            note["tags"] = tags or []
            note["updated_at"] = utc_now_iso()
            save_notes(notes)
            return note
    return None


def delete_note(note_id: str) -> bool:
    notes = load_notes()
    remaining_notes = [note for note in notes if note.get("id") != note_id]
    if len(remaining_notes) == len(notes):
        return False
    save_notes(remaining_notes)
    return True


def filter_notes(
    notes: list[dict[str, Any]],
    *,
    search: str = "",
    tag: str = "",
) -> list[dict[str, Any]]:
    search = search.strip().lower()
    tag = tag.strip().lower()
    filtered = notes
    if search:
        filtered = [
            note
            for note in filtered
            if search in note.get("title", "").lower() or search in note.get("body", "").lower()
        ]
    if tag:
        filtered = [
            note for note in filtered if tag in {item.lower() for item in note.get("tags", [])}
        ]
    return filtered


def answer_note_body(answer: str, selected_text: str | None = None) -> str:
    answer = answer.strip()
    selected = selected_text.strip() if selected_text else ""
    if selected and selected != answer:
        return f"{selected}\n\n### Full AI answer\n\n{answer}"
    return f"### AI answer\n\n{answer}"


def note_markdown(note: dict[str, Any]) -> str:
    tags = ", ".join(note.get("tags", [])) or "none"
    lines = [
        f"## {note.get('title', 'Untitled note')}",
        "",
        f"- Project: {note.get('project_id', 'default')}",
        f"- Created: {note.get('created_at', '')}",
        f"- Method: {note.get('creation_method', '')}",
        f"- Tags: {tags}",
        "",
        note.get("body", ""),
    ]
    citations = note.get("citations", [])
    if citations:
        lines.extend(["", "### Sources"])
        for index, citation in enumerate(citations, start=1):
            label = citation.get("source_label") or citation.get("source") or "Source"
            evidence = citation.get("quoted_evidence") or ""
            lines.extend([f"{index}. {label}", f"   > {evidence}"])
    return "\n".join(lines).strip() + "\n"


def export_notes_markdown(project_id: str = "default") -> str:
    return "\n\n---\n\n".join(note_markdown(note) for note in list_notes(project_id))


def save_note(note):
    create_note(title="Agent note", body=note, creation_method="agent", source_type="manual")
    if not os.path.exists(note_file):
        open(note_file, "w").close()

    with open(note_file, "a") as f:
        f.writelines([note + "\n"])

    return "Note is saved"


note_engine = FunctionTool.from_defaults(
    fn=save_note,
    name="note_saver",
    description="this tool can save a text based note to a file for the user",
)
