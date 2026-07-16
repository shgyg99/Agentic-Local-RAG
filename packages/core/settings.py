from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="EvidenceFlow", validation_alias="APP_NAME")
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_format: str = Field(default="json", validation_alias="LOG_FORMAT")

    api_key: str | None = Field(default=None, validation_alias="API_KEY")
    api_url: str | None = Field(default=None, validation_alias="API_URL")
    api_model: str | None = Field(default=None, validation_alias="API_MODEL")
    embed_model: str = Field(default="text-embedding-ada-002", validation_alias="EMBED_MODEL")
    embed_dim: int | None = Field(default=None, validation_alias="EMBED_DIM")

    postgres_url: str | None = Field(default=None, validation_alias="POSTGRES_URL")
    postgres_async_url: str | None = Field(default=None, validation_alias="POSTGRES_ASYNC_URL")
    postgres_host: str = Field(default="localhost", validation_alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, validation_alias="POSTGRES_PORT")
    postgres_user: str = Field(default="postgres", validation_alias="POSTGRES_USER")
    postgres_password: str | None = Field(default=None, validation_alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="vector_db", validation_alias="POSTGRES_DB")
    postgres_maintenance_db: str = Field(
        default="postgres",
        validation_alias="POSTGRES_MAINTENANCE_DB",
    )
    postgres_auto_create_db: bool = Field(
        default=True,
        validation_alias="POSTGRES_AUTO_CREATE_DB",
    )

    pgvector_schema: str = Field(default="public", validation_alias="PGVECTOR_SCHEMA")
    pgvector_table: str = Field(default="documents", validation_alias="PGVECTOR_TABLE")
    pdf_data_dir: Path = Field(default=Path("data"), validation_alias="PDF_DATA_DIR")
    rebuild_vector_index: bool = Field(default=False, validation_alias="REBUILD_VECTOR_INDEX")
    streamlit_port: int = Field(default=8501, validation_alias="STREAMLIT_PORT")

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        value = value.upper()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if value not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {', '.join(sorted(allowed))}.")
        return value

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, value: str) -> str:
        value = value.lower()
        allowed = {"json", "text"}
        if value not in allowed:
            raise ValueError("LOG_FORMAT must be 'json' or 'text'.")
        return value

    @field_validator("postgres_password")
    @classmethod
    def reject_placeholder_password(cls, value: str | None) -> str | None:
        if value == "password":
            raise ValueError(
                "POSTGRES_PASSWORD is still the placeholder value 'password'. "
                "Set a real password in .env."
            )
        return value

    @field_validator("embed_dim", "postgres_port", "streamlit_port")
    @classmethod
    def validate_positive_int(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("Numeric settings must be positive.")
        return value

    def resolved_embed_dim(self) -> int:
        if self.embed_dim:
            return self.embed_dim
        if self.embed_model == "text-embedding-3-large":
            return 3072
        return 1536

    def require_llm_settings(self) -> None:
        missing = []
        if not self.api_key:
            missing.append("API_KEY")
        if not self.api_model:
            missing.append("API_MODEL")
        if missing:
            raise RuntimeError(
                "Missing required LLM configuration: "
                + ", ".join(missing)
                + ". Add these values to .env."
            )


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
