from pathlib import Path

from fastapi.testclient import TestClient

import packages.notes.engine as notes_engine
from apps.api.main import app


def test_create_update_and_export_notes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(notes_engine, "NOTES_JSON_FILE", tmp_path / "notes.json")

    note = notes_engine.create_note(
        project_id="project-1",
        title="Finding",
        body="Important evidence.",
        tags=["rag"],
        citations=[
            {
                "source_label": "paper.pdf, page 2, Results",
                "quoted_evidence": "Important evidence.",
            }
        ],
        creation_method="selected_citation",
        source_type="citation",
    )
    notes_engine.update_note(note["id"], title="Updated finding", body="Edited body.", tags=["rag"])

    markdown = notes_engine.export_notes_markdown("project-1")

    assert "## Updated finding" in markdown
    assert "paper.pdf, page 2, Results" in markdown
    assert "Important evidence." in markdown


def test_notes_api_create_and_export(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(notes_engine, "NOTES_JSON_FILE", tmp_path / "api-notes.json")
    client = TestClient(app)

    response = client.post(
        "/projects/project-1/notes",
        json={
            "title": "API note",
            "body": "Saved through API.",
            "tags": ["api"],
            "citations": [{"source_label": "paper.pdf, page 1"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["title"] == "API note"
    assert client.get("/projects/project-1/notes").json()[0]["tags"] == ["api"]
    assert "API note" in client.get("/projects/project-1/notes/export").text


def test_answer_note_body_includes_full_ai_answer() -> None:
    answer = "Methodology summary\n\nThe model uses Faster R-CNN to crop formulas."

    body = notes_engine.answer_note_body(answer, "Methodology summary")

    assert "Methodology summary" in body
    assert "### Full AI answer" in body
    assert "The model uses Faster R-CNN to crop formulas." in body
