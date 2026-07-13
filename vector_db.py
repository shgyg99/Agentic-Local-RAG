import os

from llama_index.vector_stores.postgres import PGVectorStore
from sqlalchemy import select
from sqlalchemy.engine import make_url


TRUTHY_VALUES = {"1", "true", "yes", "on"}


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in TRUTHY_VALUES


def embedding_dim() -> int:
    explicit_dim = os.getenv("EMBED_DIM")
    if explicit_dim:
        return int(explicit_dim)

    embed_model = os.getenv("EMBED_MODEL", "")
    if embed_model == "text-embedding-3-large":
        return 3072
    return 1536


def postgres_urls():
    connection_url = os.getenv("POSTGRES_URL")
    if not connection_url:
        raise RuntimeError(
            "POSTGRES_URL is required. Example: "
            "postgresql://postgres:password@localhost:5432/vector_db"
        )

    url = make_url(connection_url)
    if not url.database:
        raise RuntimeError("POSTGRES_URL must include a database name.")

    sync_url = url.set(drivername="postgresql+psycopg2")
    async_url = os.getenv("POSTGRES_ASYNC_URL")
    if async_url:
        async_url = make_url(async_url).set(drivername="postgresql+asyncpg")
    else:
        async_url = url.set(drivername="postgresql+asyncpg")

    return sync_url, async_url


def get_vector_store() -> PGVectorStore:
    sync_url, async_url = postgres_urls()

    return PGVectorStore.from_params(
        connection_string=sync_url,
        async_connection_string=async_url,
        table_name=os.getenv("PGVECTOR_TABLE", "documents"),
        schema_name=os.getenv("PGVECTOR_SCHEMA", "public"),
        embed_dim=embedding_dim(),
        use_jsonb=True,
        hnsw_kwargs={
            "hnsw_m": 16,
            "hnsw_ef_construction": 64,
            "hnsw_ef_search": 40,
            "hnsw_dist_method": "vector_cosine_ops",
        },
    )


def clear_vector_store(vector_store: PGVectorStore) -> None:
    vector_store.clear()


def indexed_sources(vector_store: PGVectorStore) -> set[str]:
    vector_store._initialize()
    with vector_store._session() as session:
        source_field = vector_store._table_class.metadata_["source"].astext
        stmt = select(source_field).distinct()
        return {row[0] for row in session.execute(stmt) if row[0]}
