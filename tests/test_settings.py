from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.core.settings import AppSettings


def test_settings_resolves_large_embedding_dimension() -> None:
    settings = AppSettings(embed_model="text-embedding-3-large")

    assert settings.resolved_embed_dim() == 3072


def test_settings_uses_explicit_embedding_dimension() -> None:
    settings = AppSettings(embed_dim=768)

    assert settings.resolved_embed_dim() == 768


def test_settings_rejects_placeholder_postgres_password() -> None:
    with pytest.raises(ValidationError):
        AppSettings(postgres_password="password")


def test_pdf_data_dir_accepts_path() -> None:
    settings = AppSettings(pdf_data_dir=Path("data"))

    assert settings.pdf_data_dir == Path("data")
